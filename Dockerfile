FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
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
