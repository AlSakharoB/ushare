UV ?= uv
COMPOSE ?= docker compose
.PHONY: setup check check-backend check-frontend test-integration migrate start stop smoke api-types
setup:
	cd backend && $(UV) sync --frozen
	cd frontend && npm ci
check-backend:
	cd backend && $(UV) run ruff check . && $(UV) run ruff format --check . && $(UV) run mypy src && $(UV) run pytest -m 'not integration'
check-frontend:
	cd frontend && npm run lint && npm run typecheck && npm test && npm run build
test-integration:
	cd backend && $(UV) run pytest -m integration
migrate:
	cd backend && $(UV) run alembic upgrade head
start:
	$(COMPOSE) up -d --build
	$(COMPOSE) exec api uv run --no-sync alembic upgrade head
stop:
	$(COMPOSE) down
smoke:
	$(COMPOSE) ps
	curl --fail http://localhost:8000/health/live
	curl --fail http://localhost:8000/health/ready
	curl --fail http://localhost:8080/
api-types:
	cd backend && $(UV) run python ../scripts/export_openapi.py
	cd frontend && npm run api:types
check: check-backend check-frontend test-integration
