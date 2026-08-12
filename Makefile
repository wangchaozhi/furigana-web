.PHONY: up down logs api-dev web-dev test

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

api-dev:
	cd api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web-dev:
	cd web && npm run dev

test:
	cd api && pytest -q
