from fastapi import FastAPI

from rakshak_edge import triage  # noqa
from rakshak_edge.config import settings

app = FastAPI(title="Rakshak Edge")


@app.get("/health")
def health():
    return {"status": "ok", "model": settings["llm"]["model_name"]}


@app.post("/triage")
def triage_endpoint(message: str):
    result = triage(message)
    return result.model_dump()
