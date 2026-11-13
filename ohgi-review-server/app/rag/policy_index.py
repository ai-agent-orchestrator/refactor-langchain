"""매장 규정 분할·임베딩·Chroma 적재. 원격 임베딩은 native async."""
import hashlib
import math
from pathlib import Path
from uuid import uuid4

from anyio import to_thread
import chromadb
from chromadb.config import Settings as ChromaSettings
import httpx
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pydantic import ConfigDict

from app.core.exceptions import AiRequestError


class DemoPolicyEmbeddings(Embeddings):
    """단어/문자 해시 벡터. 실제 의미 검색 품질을 측정하는 임베더가 아니다."""
    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * 128
        groups = ("환불", "재조리", "배달", "지연", "이물질", "영업", "포장", "알레르기", "쿠폰", "개인정보", "칭찬", "예약")
        for i, word in enumerate(groups):
            if word in text:
                vector[i] += 8.0
        for i in range(max(1, len(text) - 1)):
            digest = hashlib.sha256(text[i:i + 2].encode()).digest()
            vector[16 + int.from_bytes(digest[:2], "big") % 112] += 0.1
        norm = math.sqrt(sum(x * x for x in vector)) or 1
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return await to_thread.run_sync(self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await to_thread.run_sync(self.embed_documents, texts)


class PolicyRetriever(BaseRetriever):
    # 수업 06 §6 retriever + 05 §2 embedding을 FastAPI용 async 경로로 연결.
    # 출처와 수업 대비 변경점: docs/LECTURE_TO_CODE.md
    model_config = ConfigDict(arbitrary_types_allowed=True)
    store: Chroma
    embeddings: Embeddings
    k: int = 4

    def _get_relevant_documents(self, query, *, run_manager):
        raise RuntimeError("PolicyRetriever는 await ainvoke로 사용하세요.")

    async def _aget_relevant_documents(self, query, *, run_manager):
        try:
            vector = await self.embeddings.aembed_query(query)
            # 로컬 Chroma 동기 디스크/벡터 검색만 스레드로 넘긴다.
            return await to_thread.run_sync(lambda: self.store.similarity_search_by_vector(vector, k=self.k))
        except Exception as exc:
            raise AiRequestError("매장 규정 검색에 실패했습니다. 잠시 후 다시 시도해 주세요.") from exc


def split_policy(path: Path):
    # 수업 04의 Document/분할 + 06의 metadata: 절 제목·출처·chunk ID를 잃지 않는다.
    text = path.read_text(encoding="utf-8")
    sections = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title"), ("##", "section")]).split_text(text)
    chunks = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100).split_documents(sections)
    for index, chunk in enumerate(chunks):
        chunk.metadata.update(source=path.name, chunk_id=f"policy-{index}")
        chunk.metadata.setdefault("section", "서문")
    return text, chunks


class PolicyIndex:
    def __init__(self, client, store, embeddings, collection_name, fake, http=None, async_http=None):
        self.client, self.store, self.embeddings = client, store, embeddings
        self.collection_name, self.fake = collection_name, fake
        self.http, self.async_http = http, async_http

    def retriever(self, k=4):
        return PolicyRetriever(store=self.store, embeddings=self.embeddings, k=k)

    async def close(self):
        try:
            if self.fake:
                await to_thread.run_sync(self.store.delete_collection)
            close = getattr(self.client, "close", None)
            if callable(close):
                await to_thread.run_sync(close)
        finally:
            if self.async_http:
                await self.async_http.aclose()
            if self.http:
                self.http.close()


async def build_policy_index(settings):
    # 수업 05/06: 문서 벡터를 먼저 저장한다. 문서가 같으면 매 요청 재임베딩하지 않는다.
    text, chunks = await to_thread.run_sync(split_policy, settings.policy_path)
    if not chunks:
        raise ValueError("매장 규정 문서가 비어 있습니다.")
    http = async_http = None
    if settings.fake_llm:
        embeddings = DemoPolicyEmbeddings()
        model_id = "demo-hash-v1"
    else:
        if settings.openai_api_key is None:
            raise ValueError("실제 임베딩에는 OPENAI_API_KEY가 필요합니다.")
        http, async_http = httpx.Client(), httpx.AsyncClient()
        embeddings = OpenAIEmbeddings(model=settings.embedding_model,
            api_key=settings.openai_api_key.get_secret_value(), max_retries=0,
            request_timeout=settings.openai_timeout_seconds, check_embedding_ctx_length=False,
            http_client=http, http_async_client=async_http)
        model_id = settings.embedding_model
    digest = hashlib.sha256((text + settings.policy_path.name + model_id + "split-v2-700-100").encode()).hexdigest()[:20]
    name = f"store-policy-{digest}" + (f"-{uuid4().hex[:8]}" if settings.fake_llm else "")
    owner = None
    try:
        cfg = ChromaSettings(anonymized_telemetry=False)
        client = await to_thread.run_sync(lambda: chromadb.EphemeralClient(settings=cfg) if settings.fake_llm else
            chromadb.PersistentClient(path=str(settings.chroma_path), settings=cfg))
        store = await to_thread.run_sync(lambda: Chroma(client=client, collection_name=name, embedding_function=embeddings))
        owner = PolicyIndex(client, store, embeddings, name, settings.fake_llm, http, async_http)
        collection = await to_thread.run_sync(lambda: client.get_collection(name))
        stored = await to_thread.run_sync(collection.count)
        if stored not in (0, len(chunks)):
            raise ValueError("규정 인덱스 적재가 불완전합니다. 새 인덱스로 재구축하세요.")
        if stored == 0:
            vectors = await embeddings.aembed_documents([d.page_content for d in chunks])
            for d in chunks:
                d.metadata["policy_version"] = digest
            # Chroma 공개 collection API로 미리 비동기 생성한 벡터를 적재한다.
            await to_thread.run_sync(lambda: collection.add(
                ids=[d.metadata["chunk_id"] for d in chunks], embeddings=vectors,
                documents=[d.page_content for d in chunks], metadatas=[d.metadata for d in chunks]))
        return owner
    except BaseException:
        if owner:
            await owner.close()
        else:
            if async_http:
                await async_http.aclose()
            if http:
                http.close()
        raise
