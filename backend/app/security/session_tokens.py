from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe

from app.application.models import IssuedToken


class SecureSessionTokens:
    def issue(self) -> IssuedToken:
        token = token_urlsafe(32)
        return IssuedToken(token, sha256(token.encode('ascii')).digest())

    def verify(self, token: str, verifier: bytes) -> bool:
        if not isinstance(token, str) or not isinstance(verifier, bytes) or len(verifier) != 32:
            return False
        if len(token) != 43 or not token.isascii():
            return False
        return compare_digest(sha256(token.encode('ascii')).digest(), verifier)
