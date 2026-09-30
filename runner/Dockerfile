FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WORKSPACE_ROOT=/tmp/lucio-workspaces

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium
COPY server.py ./server.py
COPY browser_qa.py ./browser_qa.py
COPY entrypoint.py ./entrypoint.py

RUN mkdir -p ${WORKSPACE_ROOT}

EXPOSE 9000
CMD ["python", "entrypoint.py"]
