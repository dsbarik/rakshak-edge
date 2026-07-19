import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT_DIR / "configs"
CONFIG_PATH = CONFIG_DIR / "base.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as file:
        settings = yaml.safe_load(file)

    llm_settings = settings.get("llm", {})

    if llm_settings.get("use_auth", False):
        settings["api_key"] = os.getenv("OLLAMA_API_KEY")
        settings["base_url"] = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")

        if not settings["api_key"]:
            raise ValueError(
                "OLLAMA_API_KEY must be set in .env when 'use_auth' is True."
            )

    else:
        settings["api_key"] = None
        settings["base_url"] = None

    return settings


settings = load_config()
