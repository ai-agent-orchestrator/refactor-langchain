from typing import Annotated

from fastapi import Depends, Request
from langchain_core.runnables import Runnable

from app.clients.llm_client import LlmClient
from app.repositories.review_repository import ReviewRepository
from app.services.reply_service import ReplyService
from app.services.graph_reply_service import GraphReplyService
from app.services.memory_reply_service import MemoryReplyService
from app.services.review_service import ReviewService


def get_repository(request: Request) -> ReviewRepository:
    return request.app.state.review_repository


def get_llm_client(request: Request) -> LlmClient:
    return request.app.state.llm_client


def get_reply_chain(request: Request) -> Runnable:
    return request.app.state.reply_chain


def get_reply_graph(request: Request):
    return request.app.state.reply_graph


def get_reply_locks(request: Request):
    return request.app.state.reply_locks


ChainDep = Annotated[Runnable, Depends(get_reply_chain)]
GraphDep = Annotated[object, Depends(get_reply_graph)]
LocksDep = Annotated[object, Depends(get_reply_locks)]
RepositoryDep = Annotated[ReviewRepository, Depends(get_repository)]
LlmDep = Annotated[LlmClient, Depends(get_llm_client)]


def get_review_service(repository: RepositoryDep) -> ReviewService:
    return ReviewService(repository)


def get_reply_service(repository: RepositoryDep, llm: LlmDep, graph: GraphDep, locks: LocksDep) -> MemoryReplyService:
    return MemoryReplyService(repository, llm, graph, locks)


ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]
ReplyServiceDep = Annotated[MemoryReplyService, Depends(get_reply_service)]
