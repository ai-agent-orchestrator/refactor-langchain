from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.llm_client import FakeLlmClient, OpenAiLlmClient
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.repositories.review_repository import ReviewRepository
from app.routers.review_router import router
from app.services.reply_service import build_reply_chain
from app.workflows.reply_graph import build_graph


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config = settings if settings is not None else get_settings()
        application.state.review_repository = ReviewRepository()
        client = (FakeLlmClient(config.fake_llm_delay_seconds) if config.fake_llm
                  else OpenAiLlmClient(config))
        application.state.llm_client = client
        try:
            application.state.reply_chain = build_reply_chain(client)
            application.state.reply_graph = build_graph(client)
            yield
        finally:
            await client.close()

    application = FastAPI(title="리뷰 관리 수업 과제", lifespan=lifespan)
    register_exception_handlers(application)
    application.include_router(router)
    return application


app = create_app()
