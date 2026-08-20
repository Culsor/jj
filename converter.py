import os
import uuid
import asyncio
import logging

import config

logger = logging.getLogger(__name__)

os.makedirs(config.TEMP_DIR, exist_ok=True)


class ConversionError(Exception):
    pass


def _tmp_path(ext: str) -> str:
    return os.path.join(config.TEMP_DIR, f"{uuid.uuid4().hex}.{ext}")


async def _run_ffmpeg(args: list, timeout: int = None):
    timeout = timeout or config.FFMPEG_TIMEOUT
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise ConversionError("Conversion timed out")

    if proc.returncode != 0:
        err_tail = stderr.decode(errors="ignore")[-1500:]
        logger.error("ffmpeg failed: %s", err_tail)
        raise ConversionError(f"ffmpeg error: {err_tail[-400:]}")

    return stdout, stderr


async def probe_has_audio(path: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return bool(stdout.decode().strip())


async def video_to_video_sticker(input_path: str) -> str:
    """
    Convert any video/gif/animation to a Telegram-compliant WEBM video sticker.
    Requirements: VP9 codec, no audio, max 3 seconds, up to 512x512 (one side must be 512),
    max ~256KB is *recommended* but Telegram allows larger for video stickers sent as files;
    for sticker set upload strict limits apply. We target the strict sticker-set spec.
    """
    output_path = _tmp_path("webm")

    vf = (
        "scale='if(gt(iw,ih),512,-2)':'if(gt(iw,ih),-2,512)',"
        "fps=30,"
        "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    )

    args = [
        "-i", input_path,
        "-t", "3",
        "-an",
        "-vf", vf,
        "-c:v", "libvpx-vp9",
        "-b:v", "256k",
        "-crf", "30",
        "-pix_fmt", "yuva420p",
        "-auto-alt-ref", "0",
        output_path,
    ]
    await _run_ffmpeg(args)
    return output_path


async def image_to_static_sticker(input_path: str) -> str:
    """Convert a static image to a Telegram-compliant WEBP sticker (512x512, one side fixed)."""
    output_path = _tmp_path("webp")
    vf = (
        "scale='if(gt(iw,ih),512,-1)':'if(gt(iw,ih),-1,512)',"
        "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    )
    args = [
        "-i", input_path,
        "-vf", vf,
        "-vframes", "1",
        output_path,
    ]
    await _run_ffmpeg(args)
    return output_path


async def sticker_to_video(input_path: str, is_animated_webm: bool) -> str:
    """
    Convert a sticker to a shareable MP4 video.
    - Static WEBP -> short MP4 (looping still, or just an image-as-video for gif-like feel)
    - Animated video sticker (WEBM/VP9) -> MP4 (H.264 + AAC-less silent audio track not required)
    """
    output_path = _tmp_path("mp4")

    if is_animated_webm:
        args = [
            "-i", input_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        # static webp -> loop into a short mp4 clip
        args = [
            "-loop", "1",
            "-i", input_path,
            "-t", "3",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-movflags", "+faststart",
            output_path,
        ]
    await _run_ffmpeg(args)
    return output_path


async def tgs_to_video(input_path: str) -> str:
    """
    Convert an animated .tgs (Lottie, gzip-compressed JSON) sticker to MP4.
    Requires 'lottie' render support via rlottie/puppeteer is complex; here we use
    a pragmatic approach with `tgs_to_gif`-style conversion through the
    `lottie` CLI convert utility if available (python `lottie` package provides `lottie_convert.py`).
    """
    output_path = _tmp_path("mp4")
    gif_path = _tmp_path("gif")

    proc = await asyncio.create_subprocess_exec(
        "lottie_convert.py", input_path, gif_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 or not os.path.exists(gif_path):
        raise ConversionError(
            "This is an animated (Lottie/.tgs) sticker and could not be rendered. "
            "Try a video sticker or static sticker instead."
        )

    args = [
        "-i", gif_path,
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        output_path,
    ]
    await _run_ffmpeg(args)

    for p in (gif_path,):
        try:
            os.remove(p)
        except OSError:
            pass

    return output_path


def cleanup(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            logger.warning("Failed to remove temp file %s", p)
