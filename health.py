import logging
from aiohttp import web

import config

logger = logging.getLogger(__name__)


async def handle_root(request):
    return web.Response(text="Sticker <-> Video bot is running.")


async def handle_health(request):
    return web.json_response({"status": "ok"})


def build_app():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    return app


async def run_health_server():
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info("Health check server listening on port %s", config.PORT)
    return runner
