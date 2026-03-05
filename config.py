import os
import sys
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Required ---
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    LOGGER_ID = int(os.getenv("LOGGER_ID", 0) or 0)

    # --- Assistant sessions ---
    STRING_SESSION = os.getenv("STRING_SESSION", "")
    STRING_SESSION2 = os.getenv("STRING_SESSION2", "")
    STRING_SESSION3 = os.getenv("STRING_SESSION3", "")

    # --- Limits ---
    DURATION_LIMIT = int(os.getenv("DURATION_LIMIT", 300)) * 60  # convert to seconds
    QUEUE_LIMIT = int(os.getenv("QUEUE_LIMIT", 30))

    # --- Feature flags ---
    AUTO_END = _str_to_bool = staticmethod(
        lambda v: v.strip().lower() in ("true", "1", "yes")
    )
    AUTO_END = os.getenv("AUTO_END", "False").strip().lower() in ("true", "1", "yes")
    AUTO_LEAVE = os.getenv("AUTO_LEAVE", "False").strip().lower() in ("true", "1", "yes")
    THUMB_GEN = os.getenv("THUMB_GEN", "True").strip().lower() in ("true", "1", "yes")

    # --- Optional ---
    COOKIE_URL = os.getenv("COOKIE_URL", "")

    @classmethod
    def check(cls):
        required = {
            "API_ID": cls.API_ID,
            "API_HASH": cls.API_HASH,
            "BOT_TOKEN": cls.BOT_TOKEN,
            "OWNER_ID": cls.OWNER_ID,
            "STRING_SESSION": cls.STRING_SESSION,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            print(f"[ERROR] Missing required env vars: {', '.join(missing)}")
            sys.exit(1)
