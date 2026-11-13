from typing import Annotated

from fastapi import Depends, Request
from langchain_core.runnables import Runnable

from app.clients.llm_client import LlmClient
from app.repositories.review_repository import ReviewRepository
from app.services.reply_service import ReplyService
from app.services.review_service import ReviewService


def get_repository(request: Request) -> ReviewRepository:
    return request.app.state.review_repository


def get_llm_client(request: Request) -> LlmClient:
    return request.app.state.llm_client


def get_reply_chain(request: Request) -> Runnable:
    return request.app.state.reply_chain


ChainDep = Annotated[Runnable, Depends(get_reply_chain)]
RepositoryDep = Annotated[ReviewRepository, Depends(get_repository)]
LlmDep = Annotated[LlmClient, Depends(get_llm_client)]


def get_review_service(repository: RepositoryDep) -> ReviewService:
    return ReviewService(repository)


def get_reply_service(repository: RepositoryDep, llm: LlmDep, chain: ChainDep) -> ReplyService:
    return ReplyService(repository, llm, chain)


ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]
ReplyServiceDep = Annotated[ReplyService, Depends(get_reply_service)]
