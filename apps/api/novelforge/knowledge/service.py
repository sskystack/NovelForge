import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.ai.providers import EmbeddingProvider, ProviderError
from novelforge.errors import Problem
from novelforge.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeStatus,
    KnowledgeVisibility,
)

CHUNKER_VERSION = "paragraph-v1"


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
        return existing
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
        if len(vectors) != len(chunks):
            raise ProviderError("embedding count does not match chunks")
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
