FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Piper TTS binary (~30MB, no PyTorch/CUDA needed)
# Using aarch64 for Apple Silicon Mac running Docker
RUN curl -L -o /tmp/piper.tar.gz \
    "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz" \
    && tar -xzf /tmp/piper.tar.gz -C /usr/local/ --strip-components=1 \
    && rm /tmp/piper.tar.gz \
    && piper --help 2>/dev/null || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p chroma_db rag_documents/legal rag_documents/medical

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
