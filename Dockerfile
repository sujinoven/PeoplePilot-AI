
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY app.py ./
COPY src/ ./src/
COPY data/ ./data/

ENV PYTHONPATH=/app

CMD ["uv", "run", "--no-sync", "python", "app.py"]
