.PHONY: install db-up db-migrate db-rollback run

# Install dependencies
install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

# Start Postgres via Docker
db-up:
	docker compose -f ../docker-compose.yml up -d db

# Apply all pending migrations
db-migrate:
	./venv/bin/alembic upgrade head

# Roll back the last migration
db-rollback:
	./venv/bin/alembic downgrade -1

# Show current migration status
db-status:
	./venv/bin/alembic current

# Start the API server
run:
	./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
