from sqlalchemy import select
from test_canon import create_novel, headers, register_and_login

from novelforge.ai.analysis_models import ChapterAnalysis
from novelforge.ai.providers import MockProvider, ProviderError


def chapter_and_version(client):
    register_and_login(client)
    novel_id = create_novel(client, "Runtime regression")
    chapter = client.post(
        f"/api/v1/novels/{novel_id}/chapters", headers=headers(client), json={"title": "Runtime"}
    ).json()
    version = client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}/versions").json()[0]
    return novel_id, chapter, version


def test_invalid_provider_returns_failed_generation_instead_of_unhandled_500(client):
    novel, chapter, _ = chapter_and_version(client)
    client.app.state.settings.ai_provider = "unconfigured"
    result = client.post(
        f"/api/v1/novels/{novel}/ai/generations",
        headers=headers(client),
        json={"chapter_id": chapter["id"]},
    )
    assert result.status_code == 202
    assert result.json()["status"] == "failed"
    assert result.json()["error_message"]


def test_generation_uses_configured_model_when_request_omits_model(client):
    novel, chapter, _ = chapter_and_version(client)
    client.app.state.settings.ai_chat_model = "configured-chat-model"
    result = client.post(
        f"/api/v1/novels/{novel}/ai/generations",
        headers=headers(client),
        json={"chapter_id": chapter["id"]},
    )
    assert result.status_code == 202
    assert result.json()["status"] == "succeeded"
    assert result.json()["model"] == "configured-chat-model"


def test_analysis_embedding_failure_preserves_analysis_and_returns_warning(client, monkeypatch):
    novel, _, version = chapter_and_version(client)

    class NoEmbeddings(MockProvider):
        def embed(self, texts, *, model="mock-embedding"):
            raise ProviderError("Embedding service unavailable")

    monkeypatch.setattr(
        "novelforge.ai.analysis_service.create_chat_provider", lambda settings: NoEmbeddings()
    )
    result = client.post(
        f"/api/v1/novels/{novel}/ai/analysis/{version['id']}", headers=headers(client)
    )
    assert result.status_code == 202
    assert result.json()["status"] == "succeeded"
    assert result.json()["warnings"]


def test_analysis_chat_failure_is_persisted_and_can_retry(client, db_session, monkeypatch):
    novel, _, version = chapter_and_version(client)

    class Unavailable(MockProvider):
        def chat(self, messages, **kwargs):
            raise ProviderError("Chat service unavailable")

    monkeypatch.setattr(
        "novelforge.ai.analysis_service.create_chat_provider", lambda settings: Unavailable()
    )
    url = f"/api/v1/novels/{novel}/ai/analysis/{version['id']}"
    assert client.post(url, headers=headers(client)).status_code == 502
    stored = db_session.scalar(select(ChapterAnalysis))
    assert stored is not None and stored.status == "failed"
    monkeypatch.setattr(
        "novelforge.ai.analysis_service.create_chat_provider", lambda settings: MockProvider()
    )
    retried = client.post(url, headers=headers(client))
    assert retried.status_code == 202
    assert retried.json()["id"] == str(stored.id)
    assert retried.json()["status"] == "succeeded"
