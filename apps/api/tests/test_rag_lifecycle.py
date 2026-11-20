from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from test_ai_tools import setup_novel

from novelforge.ai.context import compile_context
from novelforge.ai.providers import MockProvider
from novelforge.errors import Problem
from novelforge.knowledge.fts import create_index, drop_index, ranking
from novelforge.knowledge.models import KnowledgeChunk, KnowledgeVisibility
from novelforge.knowledge.service import SourceMaterial, ingest_source, search_knowledge
from novelforge.planning.models import Chapter, ChapterVersion
from novelforge.projects.models import Novel


def test_fts_chinese_english_and_safe_match_syntax(db_session):
    _, novel = setup_novel(db_session)
    ingest_source(
        db_session,
        novel.id,
        SourceMaterial(
            "manual",
            uuid4(),
            "月光",
            1,
            "灵力必须经过月光淬炼。 The moonstone compass points north.",
        ),
        MockProvider(),
    )
    assert create_index(db_session.connection()) is True
    assert ranking(db_session, novel.id, "月光淬炼")
    assert ranking(db_session, novel.id, "moonstone")
    for query in ("月光", "moonstone", 'moonstone " OR ( NOT * :'):
        assert search_knowledge(db_session, novel.id, query)
    assert db_session.execute(text("SELECT count(*) FROM knowledge_chunks")).scalar() == 1


def test_latest_revision_and_delete_lifecycle_are_reflected_in_fts(db_session):
    _, novel = setup_novel(db_session)
    source_id = uuid4()
    first = ingest_source(
        db_session,
        novel.id,
        SourceMaterial("manual", source_id, "Old", 1, "oldexclusive evidence"),
        MockProvider(),
    )
    second = ingest_source(
        db_session,
        novel.id,
        SourceMaterial("manual", source_id, "New", 2, "newexclusive evidence"),
        MockProvider(),
    )
    assert search_knowledge(db_session, novel.id, "oldexclusive") == []
    assert search_knowledge(db_session, novel.id, "newexclusive")[0]["source_revision"] == 2
    assert db_session.get(type(first), first.id) is not None
    db_session.delete(second)
    db_session.commit()
    assert search_knowledge(db_session, novel.id, "newexclusive") == []
    assert ranking(db_session, novel.id, "newexclusive") == []


def test_same_revision_is_immutable_and_model_reindex_preserves_chunk_citations(db_session):
    _, novel = setup_novel(db_session)
    source_id = uuid4()
    material = SourceMaterial("manual", source_id, "Stable", 1, "stable citation")
    document = ingest_source(db_session, novel.id, material, MockProvider())
    chunk_id = db_session.scalar(
        select(KnowledgeChunk.id).where(KnowledgeChunk.document_id == document.id)
    )
    with pytest.raises(Problem) as immutable:
        ingest_source(
            db_session,
            novel.id,
            SourceMaterial("manual", source_id, "Changed", 1, "changed text"),
            MockProvider(),
        )
    assert immutable.value.code == "KNOWLEDGE_REVISION_IMMUTABLE"
    ingest_source(
        db_session, novel.id, material, MockProvider(), embedding_model="different-local-model"
    )
    chunk = db_session.get(KnowledgeChunk, chunk_id)
    assert chunk.metadata_json["embedding_model"] == "different-local-model"
    assert chunk.id == chunk_id


def test_fts_candidates_never_bypass_novel_visibility_or_active_filters(db_session):
    user, first = setup_novel(db_session)
    second = Novel(owner_user_id=user.id, title="Other")
    db_session.add(second)
    db_session.commit()
    ingest_source(
        db_session,
        second.id,
        SourceMaterial(
            "manual", uuid4(), "Other", 1, "foreignexclusive foreignexclusive foreignexclusive"
        ),
        MockProvider(),
    )
    ingest_source(
        db_session,
        first.id,
        SourceMaterial(
            "manual", uuid4(), "Private", 1, "privatesecret", KnowledgeVisibility.PRIVATE
        ),
        MockProvider(),
    )
    assert search_knowledge(db_session, first.id, "foreignexclusive") == []
    assert search_knowledge(db_session, first.id, "privatesecret") == []


def test_missing_fts_and_embedding_failure_fall_back_without_losing_boundaries(db_session):
    _, novel = setup_novel(db_session)
    ingest_source(
        db_session,
        novel.id,
        SourceMaterial("manual", uuid4(), "Fallback", 1, "星海入口在北境。 lexical fallback"),
        MockProvider(),
    )
    drop_index(db_session.connection())

    class Broken:
        def embed(self, texts, *, model):
            raise RuntimeError("offline")

    assert (
        search_knowledge(db_session, novel.id, "北境", embedding_provider=Broken())[0]["title"]
        == "Fallback"
    )


def test_recent_chapters_are_bounded_and_context_uses_configured_embeddings(db_session):
    _, novel = setup_novel(db_session)
    earlier = Chapter(
        novel_id=novel.id,
        title="Earlier",
        chapter_number=1,
        story_order=Decimal(1),
        summary="Earlier summary",
    )
    current = Chapter(novel_id=novel.id, title="Current", chapter_number=2, story_order=Decimal(2))
    future = Chapter(novel_id=novel.id, title="Future", chapter_number=3, story_order=Decimal(3))
    db_session.add_all([earlier, current, future])
    db_session.commit()
    ingest_source(
        db_session,
        novel.id,
        SourceMaterial("manual", uuid4(), "Evidence", 1, "Moonstone requirement"),
        MockProvider(),
        embedding_model="configured-embedding",
    )

    class Recording(MockProvider):
        models = []

        def embed(self, texts, *, model):
            self.models.append(model)
            return super().embed(texts, model=model)

    provider = Recording()
    context = compile_context(
        db_session,
        novel.id,
        current.id,
        query="Moonstone",
        embedding_provider=provider,
        embedding_model="configured-embedding",
        include_recent_chapters=1,
    )
    recent = [section for section in context["sections"] if section["kind"] == "recent_chapter"]
    assert len(recent) == 1 and recent[0]["source_id"] == str(earlier.id)
    assert all(section["source_id"] != str(future.id) for section in context["sections"])
    assert provider.models == ["configured-embedding"]


def test_obsolete_chapter_version_is_not_retrieved(db_session):
    _, novel = setup_novel(db_session)
    chapter = Chapter(novel_id=novel.id, title="Edited", current_version=2)
    db_session.add(chapter)
    db_session.flush()
    old = ChapterVersion(
        novel_id=novel.id,
        chapter_id=chapter.id,
        version_number=1,
        content_format="markdown",
        markdown="obsoleteexclusive",
        plain_text="obsoleteexclusive",
        word_count=1,
    )
    db_session.add(old)
    db_session.commit()
    ingest_source(
        db_session,
        novel.id,
        SourceMaterial("chapter_version", old.id, "Old prose", 1, "obsoleteexclusive"),
        MockProvider(),
    )
    assert search_knowledge(db_session, novel.id, "obsoleteexclusive") == []
