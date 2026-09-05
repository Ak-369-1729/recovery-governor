import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "recovery_governor.db"

# Try loading .env if it exists
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

class Settings(BaseModel):
    app_name: str = "Recovery Governor"
    version: str = "1.0.0"
    track: str = "Razorpay AI Buildathon 2026 - Track 03: AI Revenue Recovery"
    db_path: Path = DB_PATH
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    
    # Deterministic Governor Policy Defaults
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    cooldown_minutes: int = int(os.getenv("COOLDOWN_MINUTES", "15"))
    customer_contact_cap: int = int(os.getenv("CUSTOMER_CONTACT_CAP", "2"))
    economic_hurdle: float = float(os.getenv("ECONOMIC_HURDLE", "10.0"))
    ai_confidence_threshold: float = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.50"))
    
    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key and len(self.gemini_api_key.strip()) > 5)
        
    @property
    def has_razorpay(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

settings = Settings()
