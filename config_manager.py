import os
import json
from dotenv import load_dotenv, set_key

ENV_FILE = ".env"
SETTINGS_FILE = "settings.json"

class ConfigManager:
    def __init__(self):
        load_dotenv(ENV_FILE)
        self.settings = self.load_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_settings(self, new_settings):
        self.settings.update(new_settings)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def set_env(self, key, value):
        set_key(ENV_FILE, key, value)
        os.environ[key] = value

    def get_env(self, key, default=""):
        return os.getenv(key, default)
