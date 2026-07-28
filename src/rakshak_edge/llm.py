from langchain_ollama import ChatOllama

from rakshak_edge.config import settings


def get_llm(model: str | None = None, temperature: float | None = None) -> ChatOllama:
    """Create a configured ChatOllama instance.

    Args:
        model: Override the model name from config (default: config's model_name).
        temperature: Override temperature (default: config's temperature).
    """
    kwargs: dict = {
        "model": model or settings["llm"]["model_name"],
        "temperature": temperature
        if temperature is not None
        else settings["llm"]["temperature"],
    }
    if settings.get("api_key"):
        kwargs["api_key"] = settings["api_key"]
    if settings.get("base_url"):
        kwargs["base_url"] = settings["base_url"]

    return ChatOllama(**kwargs)
