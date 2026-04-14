.PHONY: help build up down restart logs shell migrate superuser ps clean dev

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Academic Summarizer — Docker commands"
	@echo ""
	@echo "  Production (PostgreSQL + Nginx):"
	@echo "    make build        — Docker image yasash"
	@echo "    make up           — Barcha servislarni ishga tushirish"
	@echo "    make down         — Servislarni to'xtatish"
	@echo "    make restart      — Qayta ishga tushirish"
	@echo "    make logs         — Loglarni ko'rish"
	@echo "    make shell        — Django konteyneri ichida shell"
	@echo "    make migrate      — Ma'lumotlar bazasi migratsiyalari"
	@echo "    make superuser    — Superuser yaratish"
	@echo "    make ps           — Ishlaydigan konteynerlar"
	@echo "    make clean        — Konteyner + volume larni o'chirish"
	@echo ""
	@echo "  Development (SQLite, hot reload):"
	@echo "    make dev          — Dev serverni ishga tushirish"
	@echo ""

# ── Production ────────────────────────────────────────────────────────────────
build:
	docker compose build --no-cache

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart web

logs:
	docker compose logs -f --tail=100

shell:
	docker compose exec web python manage.py shell

migrate:
	docker compose exec web python manage.py migrate

superuser:
	docker compose exec web python manage.py createsuperuser

ps:
	docker compose ps

clean:
	docker compose down -v --remove-orphans

# ── Development ───────────────────────────────────────────────────────────────
dev:
	docker compose -f docker-compose.dev.yml up --build
