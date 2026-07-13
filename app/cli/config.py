import json
import os
from pathlib import Path
from typing import Dict, Optional

CONFIG_DIR = Path.home() / ".config" / "devops-copilot"
CONFIG_FILE = CONFIG_DIR / "config.json"
OLD_CONFIG_DIR = Path.home() / ".config" / "devops-rag"
OLD_CONFIG_FILE = OLD_CONFIG_DIR / "config.json"

def load_config() -> Optional[Dict[str, str]]:
    """Loads CLI settings from local configuration file with fallback/migration from old path."""
    if not CONFIG_FILE.exists():
        if OLD_CONFIG_FILE.exists():
            try:
                # Automatically migrate old config to the new directory
                with open(OLD_CONFIG_FILE, "r") as f:
                    old_data = json.load(f)
                save_config(old_data["server_url"], old_data["token"])
            except Exception:
                pass
        else:
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
