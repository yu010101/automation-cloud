"""Configuration loader for ai-hub."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing env: {key}")
    return val


def env_opt(key: str, default: str = "") -> str:
    return os.getenv(key, default)
