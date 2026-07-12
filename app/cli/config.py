import json
import os
from pathlib import Path
from typing import Dict, Optional

CONFIG_DIR = Path.home() / ".config" / "devops-rag"
CONFIG_FILE = CONFIG_DIR / "config.json"

def load_config() -> Optional[Dict[str, str]]:
    """Loads CLI settings (server url and JWT token) from the local configuration file."""
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None

def save_config(server_url: str, token: str) -> None:
    """Saves CLI settings to the local config.json file in the user's home config directory."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_data = {
            "server_url": server_url.rstrip("/"),
            "token": token
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        raise RuntimeError(f"Failed to save local config: {str(e)}")
