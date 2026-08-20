import os
import logging
import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType

import config
from database import db
import converter
from health import run_health_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Client(
    "sticker_video_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

START_TEXT = (
    "**Sticker ↔ Video Bot**\n\n"
    "Send me a **video / GIF / animation** and I'll turn it into a **sticker**.\n"
    "Send me a **sticker** and I'll turn it into a **video (MP4)**.\n\n"
    "Just drop the file in, no commands needed."
)


async def _check_force_sub(client: Client, message: Message) -> bool:
    if not config.FORCE_SUB_CHANNEL:
        return True
    try:
        member = await client.get_chat_member(config.FORCE_SUB_CHANNEL, message.from_user.id)
        if member.status in ("left", "kicked"):
            raise Exception("not joined")
        return True
    except Exception:
        await message.reply_text(
            f"Please join {config.FORCE_SUB_CHANNEL} first, then send your file again.",
        )
        return False


@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.first_name or "",
        message.from_user.username or "",
    )
    await message.reply_text(START_TEXT)


@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client: Client, message: Message):
    if config.OWNER_ID and message.from_user.id != config.OWNER_ID:
        return
    total_users = await db.total_users_count()
    stats = await db.get_stats()
    await message.reply_text(
        "**Bot Stats**\n\n"
        f"Users: `{total_users}`\n"
        f"Total conversions: `{stats.get('total_conversions', 0)}`\n"
        f"Video→Sticker: `{stats.get('total_video_to_sticker', 0)}`\n"
        f"Sticker→Video: `{stats.get('total_sticker_to_video', 0)}`"
    )


@app.on_message(filters.command("broadcast") & filters.private)
async def broadcast_handler(client: Client, message: Message):
    if config.OWNER_ID and message.from_user.id != config.OWNER_ID:
        return
    if not message.reply_to_message:
        await message.reply_text("Reply to a message with /broadcast to send it to all users.")
        return

    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0
    status = await message.reply_text(f"Broadcasting to {len(user_ids)} users...")

    for uid in user_ids:
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status.edit_text(f"Broadcast done.\nSent: {sent}\nFailed: {failed}")


# ---------- Video / GIF / Animation -> Sticker ----------

@app.on_message(
    filters.private
    & (filters.video | filters.animation | filters.document)
)
async def media_to_sticker_handler(client: Client, message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.first_name or "",
        message.from_user.username or "",
    )
    if not await _check_force_sub(client, message):
        return

    # If it's a document, only proceed if it looks like a video/gif
    if message.document:
        mime = (message.document.mime_type or "")
        if not (mime.startswith("video/") or mime == "image/gif"):
            return

    status_msg = await message.reply_text("Converting to sticker...")
    input_path = None
    output_path = None
    try:
        input_path = await message.download(file_name=os.path.join(config.TEMP_DIR, ""))

        size_mb = os.path.getsize(input_path) / (1024 * 1024)
        if size_mb > config.MAX_FILE_SIZE_MB:
            await status_msg.edit_text(
                f"File too large ({size_mb:.1f}MB). Max is {config.MAX_FILE_SIZE_MB}MB."
            )
            return

        output_path = await converter.video_to_video_sticker(input_path)
        await message.reply_sticker(output_path)
        await status_msg.delete()
        await db.increment_conversion(message.from_user.id, "video_to_sticker")

    except converter.ConversionError as e:
        await status_msg.edit_text(f"Conversion failed: {e}")
    except Exception as e:
        logger.exception("media_to_sticker_handler error")
        await status_msg.edit_text(f"Something went wrong: {e}")
    finally:
        converter.cleanup(input_path, output_path)


# ---------- Sticker -> Video ----------

@app.on_message(filters.private & filters.sticker)
async def sticker_to_video_handler(client: Client, message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.first_name or "",
        message.from_user.username or "",
    )
    if not await _check_force_sub(client, message):
        return

    sticker = message.sticker
    status_msg = await message.reply_text("Converting to video...")
    input_path = None
    output_path = None
    try:
        input_path = await message.download(file_name=os.path.join(config.TEMP_DIR, ""))

        if sticker.is_animated:
            # Lottie / .tgs sticker
            output_path = await converter.tgs_to_video(input_path)
        elif sticker.is_video:
            # Video (WEBM/VP9) sticker
            output_path = await converter.sticker_to_video(input_path, is_animated_webm=True)
        else:
            # Static WEBP sticker
            output_path = await converter.sticker_to_video(input_path, is_animated_webm=False)

        await message.reply_video(output_path)
        await status_msg.delete()
        await db.increment_conversion(message.from_user.id, "sticker_to_video")

    except converter.ConversionError as e:
        await status_msg.edit_text(f"Conversion failed: {e}")
    except Exception as e:
        logger.exception("sticker_to_video_handler error")
        await status_msg.edit_text(f"Something went wrong: {e}")
    finally:
        converter.cleanup(input_path, output_path)


# ---------- Photo -> Static Sticker (bonus, since it's the same domain) ----------

@app.on_message(filters.private & filters.photo)
async def photo_to_sticker_handler(client: Client, message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.first_name or "",
        message.from_user.username or "",
    )
    if not await _check_force_sub(client, message):
        return

    status_msg = await message.reply_text("Converting to sticker...")
    input_path = None
    output_path = None
    try:
        input_path = await message.download(file_name=os.path.join(config.TEMP_DIR, ""))
        output_path = await converter.image_to_static_sticker(input_path)
        await message.reply_sticker(output_path)
        await status_msg.delete()
        await db.increment_conversion(message.from_user.id, "video_to_sticker")
    except converter.ConversionError as e:
        await status_msg.edit_text(f"Conversion failed: {e}")
    except Exception as e:
        logger.exception("photo_to_sticker_handler error")
        await status_msg.edit_text(f"Something went wrong: {e}")
    finally:
        converter.cleanup(input_path, output_path)


async def main():
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    await db.ensure_indexes()

    health_runner = await run_health_server()

    await app.start()
    logger.info("Bot started.")

    try:
        await asyncio.Event().wait()
    finally:
        await app.stop()
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
