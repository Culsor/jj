# Sticker ↔ Video Bot

A Telegram bot that converts:
- **Video / GIF / Animation → Sticker** (Telegram-compliant WEBM video sticker, or WEBP for photos)
- **Sticker → Video** (MP4) — supports static WEBP, video WEBM, and animated `.tgs` (Lottie) stickers

Built with Pyrogram + MongoDB (Motor). Ships with a health-check HTTP server so it can run as a Render/Railway **web service** (they require a bound `$PORT`).

## Commands

- `/start` — welcome message
- `/stats` — (owner only) usage stats
- `/broadcast` — (owner only) reply to a message with this command to broadcast it to all users

## Local setup

1. Install system deps: `ffmpeg` (required), and for `.tgs` sticker support the `lottie` Python package needs `cairo` installed on your system (`apt install libcairo2-dev` on Debian/Ubuntu, `brew install cairo` on macOS).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in:
   - `API_ID` / `API_HASH` from https://my.telegram.org
   - `BOT_TOKEN` from [@BotFather](https://t.me/BotFather)
   - `MONGO_URI` — a MongoDB Atlas connection string (or self-hosted)
   - `OWNER_ID` — your Telegram user ID
4. Export the env vars (or use `python-dotenv` / your platform's env panel) and run:
   ```
   python bot.py
   ```

## Deploy on Render

This repo includes a `Dockerfile` + `render.yaml` (Docker env — needed because ffmpeg and cairo are system packages that Render's native Python buildpack won't install).

1. Push this repo to GitHub.
2. On Render: **New → Blueprint**, point it at the repo, it will read `render.yaml`.
3. Fill in the secret env vars (`API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_URI`, `OWNER_ID`) in the Render dashboard.
4. Deploy. Render will build the Docker image and run `python bot.py`, which binds to `$PORT` automatically for the health check.

## Deploy on Railway

Includes `railway.json` + `nixpacks.toml` + `Procfile`.

1. Push to GitHub, create a new Railway project from the repo.
2. Railway auto-detects `railway.json` and uses Nixpacks with `ffmpeg`, `cairo`, `gcc` installed via `nixpacks.toml`.
3. Set the same env vars in the Railway dashboard.
4. Deploy — Railway injects `PORT` automatically.

## Notes on sticker specs

- **Video stickers** must be VP9-encoded WEBM, no audio, ≤3 seconds, 512px on the long side. The converter enforces this automatically.
- **Static stickers** are WEBP, 512px on the long side, transparent padding.
- **Animated (`.tgs`) stickers → video** requires the `lottie` package's `lottie_convert.py` CLI (installed via `requirements.txt`, needs `cairo` at the system level — already included in the Dockerfile/nixpacks config). If a Lottie sticker fails to render in your environment, the bot will tell the user gracefully rather than crashing.
- Telegram doesn't allow bots to add stickers directly to a *sticker pack* without extra `addStickerToSet`/`createNewStickerSet` calls — this bot sends the converted sticker back as a message so the user can forward/save or manually add it to a pack. Ask if you want pack-management commands added too.

## Project structure

```
.
├── bot.py            # main Pyrogram client + handlers
├── config.py          # env-driven config
├── database.py         # MongoDB/Motor layer (users, stats)
├── converter.py         # ffmpeg/lottie conversion logic
├── health.py           # aiohttp health-check server (binds $PORT)
├── requirements.txt
├── Dockerfile          # for Render
├── render.yaml
├── railway.json
├── nixpacks.toml
├── Procfile
└── .env.example
```
