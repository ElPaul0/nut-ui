FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends nut-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates
COPY static ./static

ENV LISTEN_HOST=0.0.0.0 \
    LISTEN_PORT=8765 \
    NUT_UI_DB=/data/events.db \
    UPS_NAME=ups \
    DEFAULT_LANG=en \
    DEFAULT_THEME=dark

EXPOSE 8765
VOLUME ["/data"]

CMD ["python", "app.py"]
