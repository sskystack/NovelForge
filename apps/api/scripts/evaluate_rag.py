"""Run the bundled tiny offline RAG regression corpus in a temporary SQLite DB.

Usage: uv run python scripts/evaluate_rag.py
No API key, external model request, or user's application database is used.
"""

import json
import sys
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from novelforge.ai.providers import MockProvider
from novelforge.database import Base, create_database_engine, make_session_factory
from novelforge.identity.models import User
from novelforge.knowledge.models import KnowledgeVisibility
from novelforge.knowledge.service import SourceMaterial, ingest_source, search_knowledge
from novelforge.projects import models_registry  # noqa: F401
from novelforge.projects.models import Novel


def main():
    corpus = json.loads(
        (Path(__file__).resolve().parents[1] / "tests/fixtures/rag_regression.json").read_text(
            encoding="utf-8"
        )
    )
    with tempfile.TemporaryDirectory(prefix="novelforge-rag-evaluation-") as directory:
        engine = create_database_engine(f"sqlite:///{directory}/evaluation.db")
        Base.metadata.create_all(engine)
        try:
            with make_session_factory(engine)() as db:
                author = User(
                    email="offline-evaluation@example.invalid", password_hash="not-a-login"
                )
                db.add(author)
                db.flush()
                novels = {
                    name: Novel(owner_user_id=author.id, title=name) for name in ("alpha", "beta")
                }
                db.add_all(novels.values())
                db.commit()
                for doc in corpus["documents"]:
                    ingest_source(
                        db,
                        novels[doc["novel"]].id,
                        SourceMaterial(
                            "manual",
                            uuid5(NAMESPACE_URL, f"fixture:{doc['novel']}:{doc['key']}"),
                            doc["title"],
                            doc["revision"],
                            doc["content"],
                            KnowledgeVisibility(doc.get("visibility", "approved")),
                        ),
                        MockProvider(),
                    )
                results = []
                for case in corpus["cases"]:
                    hits = search_knowledge(db, novels[case["novel"]].id, case["query"], limit=1)
                    actual = hits[0]["title"] if hits else None
                    results.append(
                        {
                            "id": case["id"],
                            "expected_title": case["expected_title"],
                            "actual_title": actual,
                            "passed": actual == case["expected_title"],
                        }
                    )
                report = {
                    "kind": "deterministic lexical and boundary regression",
                    "semantic_quality_evaluated": False,
                    "external_model_requests": 0,
                    "cases": results,
                    "passed": sum(case["passed"] for case in results),
                    "total": len(results),
                }
                print(json.dumps(report, ensure_ascii=False, indent=2))
                if not all(case["passed"] for case in results):
                    raise SystemExit(1)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
