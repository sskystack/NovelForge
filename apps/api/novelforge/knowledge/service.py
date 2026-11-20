import hashlib
import math
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from novelforge.ai.providers import EmbeddingProvider, ProviderError
from novelforge.errors import Problem
from novelforge.knowledge.fts import create_index
from novelforge.knowledge.fts import ranking as fts_ranking
from novelforge.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeStatus,
    KnowledgeVisibility,
)
from novelforge.planning.models import Chapter, ChapterVersion

CHUNKER_VERSION = "paragraph-v1"


def validate_vectors(vectors, count):
    if not isinstance(vectors, list) or len(vectors) != count:
        raise ProviderError("Embedding count does not match input")
    if (
        any(
            not isinstance(vector, list)
            or not vector
            or len(vector) > 8192
            or any(
                not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector
            )
            for vector in vectors
        )
        or len({len(vector) for vector in vectors}) != 1
    ):
        raise ProviderError("Embedding dimensions or values are invalid")


@dataclass(frozen=True)
class SourceMaterial:
    source_type: str
    source_id: UUID | None
    title: str
    source_revision: int
    content: str
    visibility: KnowledgeVisibility = KnowledgeVisibility.APPROVED


def _chunks(content: str, max_chars: int = 1800) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    result: list[str] = []
    for paragraph in paragraphs:
        result.extend(
            paragraph[index : index + max_chars] for index in range(0, len(paragraph), max_chars)
        )
    return result or [""]


def _lexical_score(query: str, content: str) -> float:
    terms = {term.casefold() for term in re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", query)}
    words = [term.casefold() for term in re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", content)]
    if not terms or not words:
        return 0.0
    counts = {term: words.count(term) for term in terms}
    return sum(1 + __import__("math").log(count) for count in counts.values() if count) / len(terms)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _reciprocal_rank_fusion(rankings: list[list[UUID]], *, k: int = 60) -> dict[UUID, float]:
    scores: dict[UUID, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + rank)
    return scores


def search_knowledge(
    db: Session,
    novel_id: UUID,
    query: str,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str = "mock-embedding",
    visibility: tuple[KnowledgeVisibility, ...] = (KnowledgeVisibility.APPROVED,),
    limit: int = 10,
    timeout_seconds: float = 2.0,
) -> list[dict]:
    if not query.strip():
        raise Problem(
            422, "EMPTY_SEARCH_QUERY", "Search query required", "Provide non-empty search text."
        )
    limit = max(1, min(limit, 50))
    chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .join(
                KnowledgeDocument,
                (KnowledgeDocument.id == KnowledgeChunk.document_id)
                & (KnowledgeDocument.novel_id == KnowledgeChunk.novel_id),
            )
            .where(
                KnowledgeChunk.novel_id == novel_id,
                KnowledgeChunk.is_active.is_(True),
                KnowledgeDocument.novel_id == novel_id,
                KnowledgeDocument.status == KnowledgeStatus.READY,
                KnowledgeDocument.visibility.in_(visibility),
                ~exists(
                    select(ChapterVersion.id)
                    .join(
                        Chapter,
                        (Chapter.id == ChapterVersion.chapter_id)
                        & (Chapter.novel_id == ChapterVersion.novel_id),
                    )
                    .where(
                        ChapterVersion.id == KnowledgeDocument.source_id,
                        ChapterVersion.novel_id == novel_id,
                        ChapterVersion.version_number != Chapter.current_version,
                    )
                ),
            )
        ).all()
    )
    started = __import__("time").monotonic()
    lexical = sorted(
        chunks, key=lambda chunk: (-_lexical_score(query, chunk.content), str(chunk.id))
    )
    lexical = [chunk for chunk in lexical if _lexical_score(query, chunk.content) > 0]
    rankings = [[chunk.id for chunk in lexical]]
    # The FTS accelerator is optional; every candidate is intersected with the
    # already novel/visibility/active/status-filtered ORM set before fusion.
    allowed_ids = {chunk.id for chunk in chunks}
    fts_ids = [
        chunk_id
        for chunk_id in fts_ranking(db, novel_id, query, visibility=visibility)
        if chunk_id in allowed_ids
    ]
    if fts_ids:
        rankings.append(fts_ids)
    vector_rows: list[KnowledgeChunk] = []
    if embedding_provider is not None and any(chunk.embedding for chunk in chunks):
        try:
            query_vector = embedding_provider.embed([query], model=embedding_model)[0]
            vector_rows = sorted(
                (
                    chunk
                    for chunk in chunks
                    if chunk.embedding
                    and chunk.metadata_json.get("embedding_model", "mock-embedding")
                    == embedding_model
                    and len(chunk.embedding) == len(query_vector)
                ),
                key=lambda chunk: (
                    -_cosine_similarity(query_vector, chunk.embedding or []),
                    str(chunk.id),
                ),
            )
            rankings.append([chunk.id for chunk in vector_rows])
        except Exception:
            vector_rows = []
    if __import__("time").monotonic() - started > timeout_seconds:
        raise Problem(
            504, "KNOWLEDGE_SEARCH_TIMEOUT", "Search timed out", "Narrow the query or retry."
        )
    scores = _reciprocal_rank_fusion(rankings)
    by_id = {chunk.id: chunk for chunk in chunks}
    results = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], str(chunk_id)))[:limit]
    docs = {
        doc.id: doc
        for doc in db.scalars(
            select(KnowledgeDocument).where(KnowledgeDocument.novel_id == novel_id)
        ).all()
    }
    return [
        {
            "chunk_id": str(chunk_id),
            "content": by_id[chunk_id].content,
            "score": scores[chunk_id],
            "source_type": docs[by_id[chunk_id].document_id].source_type,
            "source_id": str(docs[by_id[chunk_id].document_id].source_id)
            if docs[by_id[chunk_id].document_id].source_id
            else None,
            "source_revision": docs[by_id[chunk_id].document_id].source_revision,
            "document_id": str(docs[by_id[chunk_id].document_id].id),
            "title": docs[by_id[chunk_id].document_id].title,
        }
        for chunk_id in results
    ]


def ingest_source(
    db: Session,
    novel_id: UUID,
    source: SourceMaterial,
    embedding_provider: EmbeddingProvider,
    embedding_model: str = "mock-embedding",
) -> KnowledgeDocument:
    if not source.source_type.strip() or not source.title.strip():
        raise Problem(
            422,
            "INVALID_KNOWLEDGE_SOURCE",
            "Invalid knowledge source",
            "Source type and title are required.",
        )
    create_index(db.connection())
    content_hash = hashlib.sha256(source.content.encode("utf-8")).hexdigest()
    existing = db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.novel_id == novel_id,
            KnowledgeDocument.source_type == source.source_type,
            KnowledgeDocument.source_id == source.source_id,
            KnowledgeDocument.source_revision == source.source_revision,
        )
    )
    if (
        existing is not None
        and existing.content_hash == content_hash
        and existing.status == KnowledgeStatus.READY
    ):
        indexed = db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == existing.id, KnowledgeChunk.is_active.is_(True))
            .order_by(KnowledgeChunk.chunk_index)
        ).all()
        if all(
            chunk.metadata_json.get("embedding_model", "mock-embedding") == embedding_model
            for chunk in indexed
        ):
            existing.visibility = source.visibility
            db.commit()
            return existing
        try:
            vectors = embedding_provider.embed(
                [chunk.content for chunk in indexed], model=embedding_model
            )
            validate_vectors(vectors, len(indexed))
        except Exception as exc:
            raise Problem(
                502,
                "KNOWLEDGE_EMBEDDING_FAILED",
                "Re-index failed",
                "The previous active embeddings and citations were preserved.",
            ) from exc
        for chunk, vector in zip(indexed, vectors, strict=True):
            chunk.embedding = vector
            chunk.metadata_json = {**chunk.metadata_json, "embedding_model": embedding_model}
        db.commit()
        return existing
    if existing is not None and existing.status == KnowledgeStatus.READY:
        raise Problem(
            409,
            "KNOWLEDGE_REVISION_IMMUTABLE",
            "Revision is immutable",
            "Use a new source_revision when source content changes.",
        )
    if existing is None:
        document = KnowledgeDocument(
            novel_id=novel_id,
            source_type=source.source_type,
            source_id=source.source_id,
            title=source.title,
            source_revision=source.source_revision,
            visibility=source.visibility,
            content_hash=content_hash,
            chunker_version=CHUNKER_VERSION,
            status=KnowledgeStatus.PROCESSING,
        )
    else:
        document = existing
    chunks = _chunks(source.content)
    try:
        vectors = embedding_provider.embed(chunks, model=embedding_model)
        validate_vectors(vectors, len(chunks))
        if existing is None:
            db.add(document)
            db.flush()
        prior_chunks = list(
            db.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == document.id, KnowledgeChunk.is_active.is_(True)
                )
            ).all()
        )
        new_chunks = [
            KnowledgeChunk(
                novel_id=novel_id,
                document_id=document.id,
                chunk_index=index,
                content=content,
                token_count=len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", content)),
                metadata_json={
                    "source_revision": source.source_revision,
                    "chunker_version": CHUNKER_VERSION,
                    "embedding_model": embedding_model,
                },
                embedding=vector,
                is_active=True,
            )
            for index, (content, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        db.add_all(new_chunks)
        db.flush()
        for chunk in prior_chunks:
            chunk.is_active = False
        if source.source_id is not None:
            older = db.scalars(
                select(KnowledgeChunk)
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .where(
                    KnowledgeDocument.novel_id == novel_id,
                    KnowledgeDocument.source_type == source.source_type,
                    KnowledgeDocument.source_id == source.source_id,
                    KnowledgeDocument.source_revision < source.source_revision,
                    KnowledgeChunk.is_active.is_(True),
                )
            ).all()
            for chunk in older:
                chunk.is_active = False
        document.title = source.title
        document.content_hash = content_hash
        document.chunker_version = CHUNKER_VERSION
        document.visibility = source.visibility
        document.error_message = None
        document.status = KnowledgeStatus.READY
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        if db.in_transaction():
            db.rollback()
        if existing is None:
            failed_document = KnowledgeDocument(
                novel_id=novel_id,
                source_type=source.source_type,
                source_id=source.source_id,
                title=source.title,
                source_revision=source.source_revision,
                visibility=source.visibility,
                content_hash=content_hash,
                chunker_version=CHUNKER_VERSION,
                status=KnowledgeStatus.FAILED,
                error_message=str(exc)[:2000],
            )
            db.add(failed_document)
            db.commit()
        elif existing.status == KnowledgeStatus.READY:
            raise Problem(
                502,
                "KNOWLEDGE_EMBEDDING_FAILED",
                "Embedding failed",
                "The previous active index was preserved; retry the unchanged source revision.",
            ) from exc
        else:
            existing.status = KnowledgeStatus.FAILED
            existing.error_message = str(exc)[:2000]
            db.commit()
        raise Problem(
            502,
            "KNOWLEDGE_EMBEDDING_FAILED",
            "Embedding failed",
            "The previous active index was preserved.",
        ) from exc
