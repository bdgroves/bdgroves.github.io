"""sealbox — encrypt a small JSON payload with a shared secret, stdlib only.

Used to pass FuelCast's private Garmin data (weight, body fat, energy,
recovery, food logs) from the public site's Garmin Action to the private
fuelcast repo without publishing it. Both repos hold the same FUELCAST_KEY
secret; the public file only ever contains ciphertext.

Construction: HMAC-SHA256 as a PRF in counter mode for the keystream
(encrypt-then-MAC), with separate derived keys for encryption and the
authentication tag. Format: "v1:" + base64url(nonce16 || ciphertext || tag32).
Kept byte-for-byte identical in both repos; if you change one, change both.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

_V = "v1:"


def _key(secret: str) -> bytes:
    raw = secret.strip()
    try:
        k = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(k) >= 32:
            return k
    except Exception:
        pass
    return hashlib.sha256(raw.encode()).digest()


def _derive(k: bytes, label: bytes) -> bytes:
    return hmac.new(k, label, hashlib.sha256).digest()


def _stream(k: bytes, nonce: bytes, n: int) -> bytes:
    out, i = bytearray(), 0
    while len(out) < n:
        out += hmac.new(k, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
        i += 1
    return bytes(out[:n])


def seal(obj, secret: str) -> str:
    k = _key(secret)
    ek, mk = _derive(k, b"fuelcast-enc"), _derive(k, b"fuelcast-mac")
    pt = json.dumps(obj, separators=(",", ":")).encode()
    nonce = os.urandom(16)
    ct = bytes(a ^ b for a, b in zip(pt, _stream(ek, nonce, len(pt))))
    tag = hmac.new(mk, nonce + ct, hashlib.sha256).digest()
    return _V + base64.urlsafe_b64encode(nonce + ct + tag).decode()


def unseal(token: str, secret: str):
    if not token.startswith(_V):
        raise ValueError("unknown sealbox version")
    blob = base64.urlsafe_b64decode(token[len(_V):])
    nonce, ct, tag = blob[:16], blob[16:-32], blob[-32:]
    k = _key(secret)
    ek, mk = _derive(k, b"fuelcast-enc"), _derive(k, b"fuelcast-mac")
    if not hmac.compare_digest(tag, hmac.new(mk, nonce + ct, hashlib.sha256).digest()):
        raise ValueError("sealbox: wrong key or tampered data")
    pt = bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct))))
    return json.loads(pt)
