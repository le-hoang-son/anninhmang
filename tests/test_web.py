"""Kiem thu lop web (W1): secret key khong hardcode, gioi han tan suat POST, chan 429."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config


@pytest.fixture()
def client():
    """Flask test client voi bo dem gioi han tan suat duoc xoa truoc/sau."""
    import web.app as app_module

    app_module.reset_rate_limit()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client
    app_module.reset_rate_limit()


def test_secret_key_not_hardcoded():
    """Khoa phien phai la chuoi ngau nhien, khong dung gia tri demo cu."""
    assert isinstance(config.SECRET_KEY, str)
    assert config.SECRET_KEY != "imgsign-demo-key"
    assert len(config.SECRET_KEY) >= 32


def test_rate_limit_blocks_after_max(client):
    """Sau RATE_LIMIT_MAX lan POST, request tiep theo tra 429 voi thong bao tieng Viet."""
    for i in range(config.RATE_LIMIT_MAX):
        resp = client.post("/protect", data={})
        assert resp.status_code == 400, f"lan {i + 1} khong nhu mong doi"

    blocked = client.post("/protect", data={})
    assert blocked.status_code == 429
    assert "quá nhiều" in blocked.get_data(as_text=True).lower()


# Cac dau hieu khoa rieng - tuyet doi khong duoc xuat hien trong bat ky phan hoi nao.
_PRIVATE_MARKERS = [
    b"-----BEGIN PRIVATE KEY",
    b"-----BEGIN ENCRYPTED PRIVATE KEY",
    b"ENCRYPTED PRIVATE KEY",
]


def test_no_route_leaks_private_key(client):
    """FR-17: khong route nao tra ve noi dung khoa rieng."""
    import web.app as app_module

    paths: list[str] = []
    for rule in app_module.app.url_map.iter_rules():
        if "GET" not in (rule.methods or set()):
            continue
        if "<" in rule.rule:  # bo qua route dong, se them gia tri cu the ben duoi
            continue
        paths.append(rule.rule)
    paths += [
        "/assets/IMG-0005",
        "/download/IMG-0005/png",
        "/download/IMG-0005/sig",
        "/media/signed/IMG-0005.png",
        "/keys/public.pem",
        "/logs/export.csv",
    ]

    for path in paths:
        resp = client.get(path)
        body = resp.get_data()
        for marker in _PRIVATE_MARKERS:
            assert marker not in body, f"route {path} lo noi dung khoa rieng"
            assert not body.startswith(marker)


def test_csv_guard_blocks_formula_injection():
    """FR-18: o bat dau bang = + - @ phai duoc them dau nhay don phia truoc."""
    import web.app as app_module

    assert app_module._csv_guard("=1+2") == "'=1+2"
    assert app_module._csv_guard("+cmd") == "'+cmd"
    assert app_module._csv_guard("-2") == "'-2"
    assert app_module._csv_guard("@x") == "'@x"
    assert app_module._csv_guard("bình thường") == "bình thường"
