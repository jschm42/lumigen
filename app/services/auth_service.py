from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets


class AuthService:
    def hash_password(self, password: str) -> str:
        raw = (password or "").strip()
        if len(raw) < 8:
            raise ValueError("Password must be at least 8 characters")
        salt = secrets.token_bytes(16)
        n = 2**14
        r = 8
        p = 1
        key = hashlib.scrypt(
            raw.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=64,
        )
        return "$".join(
            [
                "scrypt",
                str(n),
                str(r),
                str(p),
                base64.b64encode(salt).decode("ascii"),
                base64.b64encode(key).decode("ascii"),
            ]
        )

    def verify_password(self, password: str, encoded_hash: str) -> bool:
        raw = (password or "").strip()
        if not raw or not encoded_hash:
            return False
        parts = encoded_hash.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        try:
            n = int(parts[1])
            r = int(parts[2])
            p = int(parts[3])
            salt = base64.b64decode(parts[4])
            expected = base64.b64decode(parts[5])
        except (ValueError, TypeError, binascii.Error):
            return False

        actual = hashlib.scrypt(
            raw.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
