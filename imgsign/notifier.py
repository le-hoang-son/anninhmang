"""Gui canh bao ntfy (FR-9, Respond - RS.CO).

Chi gui khi verdict = KHONG_HOP_LE. Loi mang hoac topic rong KHONG duoc raise.
"""

from __future__ import annotations

import requests

import config


def send_alert(title: str, message: str) -> bool:
    """Gui thong bao ntfy. Tra True neu gui thanh cong, False neu loi/khong cau hinh.

    Khong bao gio nem ngoai le ra ngoai.
    """
    if not config.NTFY_TOPIC:
        return False

    url = f"{config.NTFY_URL.rstrip('/')}/{config.NTFY_TOPIC}"
    headers = {"Title": title, "Priority": "high", "Tags": "warning"}
    try:
        resp = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=5)
        return resp.status_code < 400
    except requests.RequestException:
        return False
