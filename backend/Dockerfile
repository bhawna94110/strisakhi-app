FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl build-essential libgomp1 libespeak-ng1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Cross-platform Piper: auto-detects ARM64 (Mac M2) vs x86_64 (WSL/Linux)
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz"; \
    else \
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"; \
    fi \
    && curl -fsSL -o /tmp/piper.tar.gz "$PIPER_URL" \
    && mkdir -p /tmp/piper_extract \
    && tar -xzf /tmp/piper.tar.gz -C /tmp/piper_extract \
    && find /tmp/piper_extract -name "*.so*" -exec cp {} /usr/local/lib/ \; \
    && find /tmp/piper_extract -type d -name "espeak-ng-data" -exec cp -r {} /usr/share/ \; \
    && find /tmp/piper_extract -type f -name "piper" -exec cp {} /usr/local/piper \; \
    && ldconfig \
    && chmod +x /usr/local/piper \
    && /usr/local/piper --help \
    && rm -rf /tmp/piper.tar.gz /tmp/piper_extract

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p chroma_db rag_documents/legal rag_documents/medical

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]