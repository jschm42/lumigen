FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libvulkan1 \
        mesa-vulkan-drivers \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=2.5.1     POETRY_VIRTUALENVS_CREATE=false     POETRY_NO_INTERACTION=1

COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"     && poetry install --only main --no-root     && pip uninstall -y poetry     && rm -rf /root/.cache

COPY alembic.ini ./
COPY VERSION ./
COPY alembic ./alembic
COPY app ./app
COPY docker ./docker-assets

RUN set -eux; \
    if [ -f /app/docker-assets/realesrgan-ncnn-vulkan ]; then \
        install -m 0755 /app/docker-assets/realesrgan-ncnn-vulkan /usr/local/bin/realesrgan-ncnn-vulkan; \
    fi

ENV UPSCALER_COMMAND=/usr/local/bin/realesrgan-ncnn-vulkan

RUN mkdir -p /app/data

EXPOSE 7003

CMD ["bash", "-c", "alembic upgrade head && python -m app.main"]
