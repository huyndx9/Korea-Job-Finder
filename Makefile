# VietJob Korea AI — task runner cho Linux/macOS/CI.
# Trên Windows dùng .\make.ps1 với đúng các target tên giống nhau.

SHELL := /bin/bash
API_DIR := apps/api
WEB_DIR := apps/web
VENV := $(API_DIR)/.venv
PY := $(VENV)/bin/python

.PHONY: help install env api web worker db-setup db-check migrate migration db-downgrade \
        test test-api test-web lint format typecheck check build clean

help:
	@echo "VietJob Korea AI — các lệnh có sẵn"
	@echo ""
	@echo "  install      Cài dependency backend + frontend"
	@echo "  env          Tạo .env từ .env.example"
	@echo "  api          Khởi động backend  (http://127.0.0.1:8000)"
	@echo "  web          Khởi động frontend (http://localhost:5173)"
	@echo "  worker       Khởi động background worker"
	@echo "  migrate      Áp dụng migration"
	@echo "  migration    Sinh migration mới:  make migration m='mo ta'"
	@echo "  test         Chạy toàn bộ test"
	@echo "  lint         Lint backend + frontend"
	@echo "  format       Format backend + frontend"
	@echo "  typecheck    mypy + tsc"
	@echo "  check        lint + typecheck + test"
	@echo "  build        Build frontend production"
	@echo "  clean        Xoá cache và file build"

install:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r $(API_DIR)/requirements-dev.txt
	npm install
	$(MAKE) env

env:
	@if [ -f .env ]; then \
		echo "!   .env đã tồn tại — không ghi đè."; \
	else \
		cp .env.example .env; \
		echo "OK  Đã tạo .env — hãy điền mật khẩu MySQL vào DATABASE_URL."; \
	fi

api:
	cd $(API_DIR) && ../../$(PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web:
	cd $(WEB_DIR) && npm run dev

worker:
	cd $(API_DIR) && ../../$(PY) -m app.workers.run

db-setup:
	@echo "1. Sửa mật khẩu trong scripts/mysql_setup.sql, lưu thành mysql_setup.local.sql"
	@echo "2. mysql -u root -p < scripts/mysql_setup.local.sql"
	@echo "3. Điền cùng mật khẩu đó vào .env"
	@echo "4. make db-check && make migrate"

db-check:
	cd $(API_DIR) && ../../$(PY) -m app.cli.dbcheck

migrate:
	cd $(API_DIR) && ../../$(PY) -m alembic upgrade head

migration:
	@test -n "$(m)" || (echo "Cần mô tả: make migration m='mo ta thay doi'" && exit 1)
	cd $(API_DIR) && ../../$(PY) -m alembic revision --autogenerate -m "$(m)"
	@echo "!   Hãy ĐỌC LẠI file migration vừa sinh trước khi chạy migrate."

db-downgrade:
	cd $(API_DIR) && ../../$(PY) -m alembic downgrade -1

test-api:
	cd $(API_DIR) && ../../$(PY) -m pytest

test-web:
	cd $(WEB_DIR) && npm run test

test: test-api test-web

lint:
	cd $(API_DIR) && ../../$(PY) -m ruff check .
	cd $(API_DIR) && ../../$(PY) -m ruff format --check .
	cd $(WEB_DIR) && npm run lint

format:
	cd $(API_DIR) && ../../$(PY) -m ruff check --fix .
	cd $(API_DIR) && ../../$(PY) -m ruff format .
	npm run format

typecheck:
	cd $(API_DIR) && ../../$(PY) -m mypy app tests
	cd $(WEB_DIR) && npm run typecheck

check: lint typecheck test
	@echo "OK  Tất cả kiểm tra đã qua"

build:
	cd $(WEB_DIR) && npm run build

clean:
	rm -rf $(API_DIR)/.pytest_cache $(API_DIR)/.mypy_cache $(API_DIR)/.ruff_cache
	rm -rf $(API_DIR)/htmlcov $(WEB_DIR)/dist $(WEB_DIR)/coverage
	find $(API_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
