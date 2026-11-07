.PHONY: setup dev-api dev-web test test-api test-web lint typecheck

setup:
	./scripts/setup.sh

dev-api:
	uv run --directory apps/api uvicorn novelforge.main:app --reload

dev-web:
	cd apps/web && npm run dev

test: test-api test-web

test-api:
	uv run --directory apps/api pytest

test-web:
	cd apps/web && npm test

lint:
	uv run --directory apps/api ruff check .
	cd apps/web && npm run lint

typecheck:
	cd apps/web && npm run typecheck
