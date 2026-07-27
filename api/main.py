from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from rakshak_edge import triage  # noqa
from rakshak_edge.config import settings
from rakshak_edge.schema import TriageOutput

app = FastAPI(
    title="Rakshak Edge",
    description="Agentic disaster message triage: parse, verify, and prioritize emergency SMS from the field.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriageRequest(BaseModel):
    message: str = Field(min_length=1, description="Raw disaster SMS or field report")


class ErrorResponse(BaseModel):
    detail: str


HERE = Path(__file__).parent
STATIC = HERE / "static"
TEMPLATES = HERE / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES))


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, message: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"original_message": message},
    )


@app.post("/", response_class=HTMLResponse)
async def root_triage(request: Request, message: str = Form(...)):
    try:
        result = await triage(message)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"result": result.model_dump(mode="json", by_alias=True), "original_message": message},
        )
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": str(e), "original_message": message},
        )


@app.get("/health")
def health():
    return {"status": "ok", "model": settings["llm"]["model_name"]}


@app.post(
    "/triage",
    response_model=TriageOutput,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def triage_endpoint(body: TriageRequest):
    try:
        return await triage(body.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Triage failed")
