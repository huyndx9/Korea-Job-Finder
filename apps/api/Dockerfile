# ⚠️ CHƯA KIỂM CHỨNG — Docker không có trên máy phát triển. Xem README.
#
# Build nhiều tầng: tầng builder chứa toolchain biên dịch (asyncmy, lxml,
# cryptography đều có phần C), tầng runtime chỉ chứa thư viện đã cài.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      default-libmysqlclient-dev \
      pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# curl phục vụ healthcheck; libmariadb3 là thư viện runtime của MySQL client.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

# Chạy bằng user không phải root: nếu ứng dụng bị chiếm quyền, kẻ tấn công
# không có root ngay trong container.
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser . .

RUN mkdir -p /app/data/resumes /app/data/cache \
    && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

# Không dùng --reload ở image này: reload theo dõi filesystem, tốn CPU và
# không phù hợp cho môi trường triển khai.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
