FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV USE_VLM=0
ENV USE_HEAVY_MODELS=0

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000 8001 8501 5000

CMD ["python", "scripts/api_server.py"]
