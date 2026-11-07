from uuid import uuid4

from novelforge.ai.providers import MockProvider
from novelforge.identity.models import User
from novelforge.identity.security import password_hasher
from novelforge.knowledge.models import KnowledgeVisibility
from novelforge.knowledge.service import SourceMaterial, ingest_source, search_knowledge
from novelforge.projects.models import Novel


def _novel(db_session, title: str) -> Novel:
    user = User(
        email=f"{title}@example.com",
        password_hash=password_hasher.hash("correct horse battery staple"),
    )
    db_session.add(user)
    db_session.flush()
    novel = Novel(owner_user_id=user.id, title=title)
    db_session.add(novel)
    db_session.commit()
    return novel


def test_search_uses_rrf_provenance_and_hard_novel_filter(db_session) -> None:
    first = _novel(db_session, "first")
    second = _novel(db_session, "second")
    provider = MockProvider()
    ingest_source(
        db_session,
        first.id,
        SourceMaterial("chapter", uuid4(), "First", 3, "星海入口在北境。"),
        provider,
    )
    ingest_source(
        db_session,
        second.id,
        SourceMaterial("chapter", uuid4(), "Second", 3, "星海入口在南境。"),
        provider,
    )
    results = search_knowledge(db_session, first.id, "北境", embedding_provider=provider)
    assert len(results) == 1
    assert results[0]["source_revision"] == 3
    assert results[0]["title"] == "First"
    assert all(item["source_id"] for item in results)


def test_search_falls_back_to_lexical_when_embeddings_are_unavailable(db_session) -> None:
    novel = _novel(db_session, "lexical")
    ingest_source(
        db_session,
        novel.id,
        SourceMaterial("canon", uuid4(), "Rule", 1, "灵力必须经过月光淬炼。"),
        MockProvider(),
    )

    class BrokenProvider:
        def embed(self, texts, *, model):
            raise RuntimeError("embedding service unavailable")

    results = search_knowledge(db_session, novel.id, "月光", embedding_provider=BrokenProvider())
    assert results and "月光" in results[0]["content"]


def test_search_excludes_draft_visibility_by_default(db_session) -> None:
    novel = _novel(db_session, "visibility")
    ingest_source(
        db_session,
        novel.id,
        SourceMaterial("draft", uuid4(), "Draft", 1, "秘密草稿", KnowledgeVisibility.DRAFT),
        MockProvider(),
    )
    assert search_knowledge(db_session, novel.id, "秘密", embedding_provider=MockProvider()) == []
