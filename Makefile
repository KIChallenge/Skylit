# Headless workers may run only `make` and `npm` outside their sandbox.
# Every backend command an agent needs gets a target here.
.PHONY: record-demo check-demo run test test-one lint smoke eval eval-all ingest seed-reset dump-fields openapi
.PHONY: frontend-setup frontend-check frontend-lint frontend-typecheck frontend-build frontend-unit frontend-dev frontend-browser

frontend-setup:
	npm --prefix frontend ci --no-audit --no-fund

frontend-check:
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck
	npm --prefix frontend run build

frontend-lint:
	npm --prefix frontend run lint

frontend-typecheck:
	npm --prefix frontend run typecheck

frontend-build:
	npm --prefix frontend run build

frontend-unit:
	npm --prefix frontend run test:unit -- $(ARGS)

frontend-dev:
	npm --prefix frontend run dev

frontend-browser:
	cd frontend && npm exec -- playwright $(ARGS)

# Export API schemas without a database connection or a running server.
openapi:
	cd backend && uv run python -c 'import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))'

run:
	docker compose up --build

test:
	cd backend && uv run pytest -q

# make test-one T=tests/test_forms.py
test-one:
	cd backend && uv run pytest -q $(T)

lint:
	cd backend && uv run ruff check . ../eval

smoke:
	uv run backend/scripts/smoke_eustella.py

eval:
	PYTHONPATH="$(CURDIR)/backend:$(CURDIR)" uv run --project backend python -m eval.run --set $(SET) $(ARGS)

eval-all:
	$(MAKE) eval SET=all ARGS="$(ARGS)"

ingest:
	cd backend && uv run python -m app.rag.ingest

# Replaces personas, Leistungen and offices in the running stack; deletes demo conversations.
seed-reset:
	docker compose exec backend python -m app.seed --reset

# make dump-fields PDF=seed/forms/pdf/pva_pflegegeld.pdf
dump-fields:
	cd backend && uv run python -m app.forms.dump_fields $(PDF)

# Backend must run (LLM_PROVIDER=eustella LLM_RECORD=1 to record, replay to check).
record-demo:
	cd backend && uv run python -m scripts.record_demo --base-url http://localhost:$${BACKEND_PORT:-8000}

check-demo:
	cd backend && uv run python -m scripts.record_demo --base-url http://localhost:$${BACKEND_PORT:-8000} --check
