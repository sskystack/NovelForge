from uuid import uuid4

import pytest

from novelforge.ai.providers import MockProvider, ProviderError
from novelforge.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeStatus
from novelforge.knowledge.service import SourceMaterial, ingest_source


def test_ingestion_is_idempotent_and_preserves_source_provenance(db_session) -> None:
    from novelforge.identity.models import User
    from novelforge.identity.security import password_hasher
    from novelforge.projects.models import Novel

    user = User(
        email="knowledge@example.com",
        password_hash=password_hasher.hash("correct horse battery staple"),
    )
    db_session.add(user)
    db_session.flush()
    novel = Novel(owner_user_id=user.id, title="Knowledge")
    db_session.add(novel)
    db_session.commit()
    source = SourceMaterial(
        "chapter_version", uuid4(), "Chapter 1", 7, "第一段。\n\nSecond paragraph."
    )
    first = ingest_source(db_session, novel.id, source, MockProvider())
    second = ingest_source(db_session, novel.id, source, MockProvider())
    chunks = db_session.query(KnowledgeChunk).filter_by(document_id=first.id).all()
    assert first.id == second.id
    assert first.source_revision == 7
    assert first.content_hash == second.content_hash
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert all(chunk.metadata_json["source_revision"] == 7 for chunk in chunks)
    assert all(chunk.novel_id == novel.id and chunk.is_active for chunk in chunks)
    assert db_session.query(KnowledgeDocument).filter_by(novel_id=novel.id).count() == 1


def test_failed_reingestion_keeps_previous_active_chunks(db_session) -> None:
    from novelforge.errors import Problem
    from novelforge.identity.models import User
    from novelforge.identity.security import password_hasher
    from novelforge.projects.models import Novel

    user = User(
        email="failure@example.com",
        password_hash=password_hasher.hash("correct horse battery staple"),
    )
    db_session.add(user)
    db_session.flush()
    novel = Novel(owner_user_id=user.id, title="Retry")
    db_session.add(novel)
    db_session.commit()
    source_id = uuid4()
    first = ingest_source(
        db_session,
        novel.id,
        SourceMaterial("canon", source_id, "Canon", 1, "Old fact."),
        MockProvider(),
    )

    class FailingProvider:
        def embed(self, texts, *, model):
            raise ProviderError("upstream unavailable")

    with pytest.raises(Problem) as error:
        ingest_source(
            db_session,
            novel.id,
            SourceMaterial("canon", source_id, "Canon", 2, "New fact."),
            FailingProvider(),
        )
    assert error.value.code == "KNOWLEDGE_EMBEDDING_FAILED"
    active = db_session.query(KnowledgeChunk).filter_by(novel_id=novel.id, is_active=True).all()
    assert len(active) == 1 and active[0].content == "Old fact."
    old_document = db_session.get(KnowledgeDocument, first.id)
    assert old_document is not None and old_document.status == KnowledgeStatus.READY
    failed = db_session.query(KnowledgeDocument).filter_by(source_revision=2).one()
    assert failed.status == KnowledgeStatus.FAILED
