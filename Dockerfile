FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py transcribe_task.py ./
COPY static ./static
RUN useradd -m studio && mkdir /app/data /app/models && chown -R studio:studio /app
USER studio
ENV WHISPER_MODEL=tiny
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-tiny', local_dir='/app/models/tiny', allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.txt'])"
ENV WHISPER_MODEL=/app/models/tiny
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
