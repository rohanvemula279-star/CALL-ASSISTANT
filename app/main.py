import structlog
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.dependencies import get_container, get_piper
from app.logger import get_logger, setup_logging
from app.routers import chat as chat_router
from app.routers import greeting as greeting_router
from app.routers import helpers as helpers_router
from app.routers import incoming_call as incoming_call_router
from app.routers import meta as meta_router
from app.routers import speak as speak_router
from app.routers import transcribe as transcribe_router
from app.routers import voicemail as voicemail_router

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    container = get_container()

    log.info(
        "app.starting",
        env=settings.environment,
        ollama=settings.ollama_host,
        model=settings.ollama_model,
    )

    await container.store.startup()
    await container.ollama.startup()
    await container.telegram.startup()
    await container.livekit.startup()

    import asyncio

    await asyncio.to_thread(container.whisper.startup)
    await asyncio.to_thread(container.piper.startup)

    log.info("app.ready", port=settings.app_port)
    try:
        yield
    finally:
        log.info("app.shutting_down")
        await container.ollama.shutdown()
        await container.telegram.shutdown()
        await container.livekit.shutdown()
        await container.store.shutdown()
        await asyncio.to_thread(container.whisper.shutdown)
        await asyncio.to_thread(container.piper.shutdown)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Rohan Call Assistant",
        description="Auto-answer calls, record voicemails, transcribe with Whisper, notify via Telegram",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router.router)
    app.include_router(transcribe_router.router)
    app.include_router(speak_router.router)
    app.include_router(incoming_call_router.router)
    app.include_router(voicemail_router.router)
    app.include_router(greeting_router.router)
    app.include_router(helpers_router.router)
    app.include_router(meta_router.router)

    piper = get_piper()
    piper.output_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/storage/tts",
        StaticFiles(directory=str(piper.output_dir)),
        name="tts",
    )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.error("request.unhandled", path=str(request.url), error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)},
        )

    return app


app = create_app()
