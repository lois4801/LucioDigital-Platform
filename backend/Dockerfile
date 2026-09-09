FROM python:3.11-slim

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# emergentintegrations lives on the Emergent index; harmless to skip when self-hosting with your own keys.
RUN pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt

COPY . .

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
