# Chạy Backend

## Yêu cầu

- Python 3.11+
- Docker Desktop (cho Postgres + Redis)

---

## 1. Lần đầu setup

```powershell
# Windows
.\scripts\bootstrap.ps1
```

```bash
# Git Bash / Linux / macOS
./scripts/bootstrap.sh
```

Bootstrap sẽ tự động:
- Tạo `.env` từ `.env.example`
- Khởi động Postgres + Redis qua Docker
- Tạo `.venv` và cài dependencies

---

## 2. Khởi động infrastructure

```bash
docker compose -f docker-compose.yml up -d
```

| Service  | Port |
|----------|------|
| Postgres | 5432 |
| Redis    | 6379 |

---

## 3. Chạy migration DB

```bash
.venv/Scripts/python.exe -m alembic upgrade head
# hoặc Linux/macOS:
.venv/bin/python -m alembic upgrade head
```

---

## 4. Chạy các service

Mở **4 terminal riêng biệt**:

**Terminal 1 — API server**
```bash
.venv/Scripts/python.exe -m uvicorn apps.api.app.main:app --reload --reload-dir apps --reload-dir libs --port 8000
# hoặc dùng script:
.\scripts\dev.ps1
```

**Terminal 2 — Celery worker (strategy + risk + notify)**
```bash
.venv/Scripts/python.exe -m celery -A apps.worker.celery_app worker --pool=solo -l info -Q celery
```

**Terminal 3 — Celery worker (execution)**
```bash
.venv/Scripts/python.exe -m celery -A apps.worker.celery_app worker --pool=solo -l info -Q execution --concurrency=1
```

**Terminal 4 — Celery beat (scheduler)**
```bash
.venv/Scripts/python.exe -m celery -A apps.worker.celery_app beat -l info
```

> **Windows:** dùng `--pool=solo`. Linux/macOS dùng `--pool=prefork` (mặc định).

---

## 5. Chạy indexer (đồng bộ vault từ subgraph)

Indexer chạy qua Celery Beat — không cần chạy thủ công.

```bash
# Chạy 1 lần (thủ công / test)
.venv/Scripts/python.exe -m apps.indexer.main
```

Xem `make beat` để chạy scheduler.

---

## 6. Kiểm tra

```bash
# Health check
curl http://localhost:8000/health

# DB ready check
curl http://localhost:8000/api/v1/ready

# Danh sách vault
curl http://localhost:8000/api/v1/vaults
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 7. Deploy (Production)

Chạy tất cả 5 service bằng 1 lệnh duy nhất:

```bash
# Build image và khởi động tất cả service
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Xem logs (tất cả service)
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Xem logs 1 service cụ thể
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api

# Dừng tất cả
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

| Service | Mô tả |
|---------|-------|
| `api` | FastAPI + auto-migrate khi khởi động |
| `worker` | Celery worker xử lý queue `celery` |
| `worker-exec` | Celery worker xử lý queue `execution` (concurrency=1) |
| `beat` | Celery beat scheduler |
| `indexer` | Đồng bộ vault từ subgraph (Celery Beat, INDEXER_TICK_SECONDS) |

> **Lưu ý:** Cần có file `.env` ở thư mục gốc trước khi chạy.

---

## Biến môi trường quan trọng (`.env`)

| Biến | Mô tả |
|------|-------|
| `BASE_RPC_URL` | RPC endpoint cho Base Sepolia (Alchemy/Infura) |
| `EXECUTOR_PRIVATE_KEY` | Private key ví executor (ký transaction) |
| `EXECUTOR_DRY_RUN` | `true` = chỉ simulate, không gửi tx thật |
| `SUBGRAPH_URL` | GraphQL endpoint của subgraph |
| `SUBGRAPH_API_KEY` | API key The Graph |
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram (tuỳ chọn, cho alert) |
| `TELEGRAM_CHAT_ID` | Chat ID nhận alert (tuỳ chọn) |
| `EXECUTION_COOLDOWN_SECONDS` | Thời gian chờ tối thiểu giữa 2 lần execute cùng vault (mặc định `3600`) |
