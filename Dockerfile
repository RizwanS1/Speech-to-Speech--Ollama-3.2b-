FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VOSK_MODEL_PATH=/app/models/vosk-model-small-en-us-0.15

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        espeak-ng \
        libasound2 \
        libespeak1 \
        unzip \
    && rm -rf /var/lib/apt/lists/*

COPY assistant/server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY assistant/__init__.py ./assistant/__init__.py
COPY assistant/server ./assistant/server

RUN mkdir -p /app/models \
    && curl -fsSL "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" -o /tmp/vosk-model.zip \
    && unzip -q /tmp/vosk-model.zip -d /app/models \
    && rm /tmp/vosk-model.zip

EXPOSE 8000

CMD ["uvicorn", "assistant.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
