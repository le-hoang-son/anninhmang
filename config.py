"""Cau hinh chung cho he thong ImgSign.

Moi duong dan deu dung pathlib.Path, goc la thu muc chua file config.py.
"""

import os
from pathlib import Path

# Thu muc goc du an (thu muc chua config.py)
BASE_DIR: Path = Path(__file__).resolve().parent

# --- Cau hinh nguoi phat hanh ---
OWNER_NAME: str = "Truong Demo"

# --- Thong bao ntfy ---
NTFY_URL: str = "https://ntfy.sh"
NTFY_TOPIC: str = os.environ.get("IMGSIGN_NTFY_TOPIC", "")  # rong = tat canh bao

# --- Khoa rieng ---
KEY_PASSWORD: str = os.environ.get("IMGSIGN_KEY_PASSWORD", "")  # rong = khong ma hoa khoa

# --- Gioi han upload ---
MAX_UPLOAD_MB: int = 10

# --- Duong dan thu muc / file ---
KEYS_DIR: Path = BASE_DIR / "keys"
DATA_DIR: Path = BASE_DIR / "data"
SAMPLES_DIR: Path = BASE_DIR / "samples"

ORIGINALS_DIR: Path = DATA_DIR / "originals"
SIGNED_DIR: Path = DATA_DIR / "signed"
LOGS_DIR: Path = DATA_DIR / "logs"

ASSETS_FILE: Path = DATA_DIR / "assets.json"
VERIFY_LOG: Path = LOGS_DIR / "verify.log"

PRIVATE_KEY_FILE: Path = KEYS_DIR / "private.pem"
PUBLIC_KEY_FILE: Path = KEYS_DIR / "public.pem"
