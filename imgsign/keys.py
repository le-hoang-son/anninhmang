"""Tao va nap khoa RSA-2048 (FR-1).

Khoa rieng luu dang PEM/PKCS8 tai keys/private.pem. Neu bien moi truong
IMGSIGN_KEY_PASSWORD duoc dat, khoa rieng se duoc ma hoa bang mat khau do.
"""

from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

import config


def key_fingerprint(public_key: RSAPublicKey) -> str:
    """Tra ve van tay khoa: 16 ky tu hex dau cua SHA-256 tren public key DER."""
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]


def _key_password_bytes() -> bytes | None:
    """Tra ve mat khau khoa dang bytes, hoac None neu khong dat."""
    return config.KEY_PASSWORD.encode("utf-8") if config.KEY_PASSWORD else None


def generate_keys(force: bool = False) -> str:
    """Sinh cap khoa RSA-2048 va luu vao keys/.

    Khong ghi de neu khoa da ton tai, tru khi force=True.
    Nem FileExistsError neu da co khoa va force=False.
    Tra ve van tay khoa cong khai.
    """
    if not force and (config.PRIVATE_KEY_FILE.exists() or config.PUBLIC_KEY_FILE.exists()):
        raise FileExistsError("Khoa đã tồn tại")

    config.KEYS_DIR.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    password = _key_password_bytes()
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    config.PRIVATE_KEY_FILE.write_bytes(private_pem)
    config.PUBLIC_KEY_FILE.write_bytes(public_pem)

    return key_fingerprint(private_key.public_key())


def load_private_key() -> RSAPrivateKey:
    """Nap khoa rieng tu keys/private.pem (giai ma neu co mat khau)."""
    data = config.PRIVATE_KEY_FILE.read_bytes()
    return serialization.load_pem_private_key(data, password=_key_password_bytes())


def load_public_key() -> RSAPublicKey:
    """Nap khoa cong khai tu keys/public.pem."""
    data = config.PUBLIC_KEY_FILE.read_bytes()
    return serialization.load_pem_public_key(data)
