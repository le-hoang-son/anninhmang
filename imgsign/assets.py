"""Bang tai san anh (FR-8, Identify - ID.AM) luu tai data/assets.json.

Moi tai san: asset_id (IMG-0001), name, type, importance (1-3), sha256_original, created_at.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

import config

_ASSET_ID_RE = re.compile(r"^IMG-(\d{4})\.")


def _load_all() -> list[dict]:
    """Doc toan bo danh sach tai san, tra ve [] neu file chua co."""
    if not config.ASSETS_FILE.exists():
        return []
    try:
        data = json.loads(config.ASSETS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save_all(assets: list[dict]) -> None:
    """Ghi danh sach tai san ra file JSON."""
    config.ASSETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.ASSETS_FILE.write_text(
        json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _max_existing_id() -> int:
    """So thu tu lon nhat da dung, tinh ca assets.json va file trong data/signed/."""
    max_n = 0
    for a in _load_all():
        m = _ASSET_ID_RE.match(str(a.get("asset_id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    if config.SIGNED_DIR.exists():
        for p in config.SIGNED_DIR.glob("IMG-*"):
            m = _ASSET_ID_RE.match(p.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return max_n


def register_asset(name: str, asset_type: str, importance: int, sha256_original: str) -> dict:
    """Dang ky tai san moi, sinh asset_id dang IMG-0001. Tra ve dict tai san."""
    assets = _load_all()

    asset = {
        "asset_id": f"IMG-{_max_existing_id() + 1:04d}",
        "name": name,
        "type": asset_type,
        "importance": importance,
        "sha256_original": sha256_original,
        "created_at": datetime.now().astimezone().isoformat(),
    }
    assets.append(asset)
    _save_all(assets)
    return asset


def list_assets() -> list[dict]:
    """Tra ve danh sach tai san."""
    return _load_all()


def get_asset(asset_id: str) -> dict | None:
    """Tim tai san theo asset_id, None neu khong co."""
    for a in _load_all():
        if a.get("asset_id") == asset_id:
            return a
    return None
