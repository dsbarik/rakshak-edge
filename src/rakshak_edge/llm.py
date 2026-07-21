from langchain_ollama import ChatOllama

from rakshak_edge.config import settings


def get_llm() -> ChatOllama:
    kwargs = {
        "model": settings["llm"]["model_name"],
        "temperature": settings["llm"]["temperature"],
    }
    if settings.get("base_url"):
        kwargs["base_url"] = settings["base_url"]

    return ChatOllama(**kwargs)
