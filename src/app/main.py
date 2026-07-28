from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from rakshak_edge import triage
from rakshak_edge.config import settings
from rakshak_edge.schema import TriageOutput

limiter = Limiter(key_func=get_remote_address)

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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
@limiter.limit("5/minute")
async def root_triage(request: Request, message: str = Form(...)):
    try:
        result = await triage(message)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "result": result.model_dump(mode="json", by_alias=True),
                "original_message": message,
            },
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
@limiter.limit("5/minute")
async def triage_endpoint(body: TriageRequest, request: Request):
    try:
        return await triage(body.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Triage failed")
