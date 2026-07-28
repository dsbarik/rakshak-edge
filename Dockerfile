FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install uv --quiet && uv sync --frozen && uv cache clean

CMD ["uv", "run", "fastapi", "run"]
