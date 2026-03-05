"""Configuration loader for influencer-agent."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config(path: Path | None = None) -> dict:
    """Load YAML config, merging with environment variables."""
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config


def get_env(key: str) -> str:
    """Get required environment variable or raise."""
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


def get_env_optional(key: str, default: str = "") -> str:
    """Get optional environment variable."""
    return os.getenv(key, default)
