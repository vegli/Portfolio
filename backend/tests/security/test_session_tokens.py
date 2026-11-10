from hashlib import sha256

import pytest

from app.security.session_tokens import SecureSessionTokens


def test_secure_issuance_and_verification():
    tokens = SecureSessionTokens()
    issued = [tokens.issue() for _ in range(100)]
    assert len({i.token for i in issued}) == 100
    for item in issued:
        assert len(item.token) == 43
        assert item.verifier == sha256(item.token.encode('ascii')).digest()
        assert tokens.verify(item.token, item.verifier)
        assert item.token not in repr(item)
    assert not tokens.verify(issued[0].token, issued[1].verifier)


@pytest.mark.parametrize('token', ['', 'wrong', 'é' * 43, 'x' * 10000, None, b'bytes'])
def test_invalid_tokens(token):
    service = SecureSessionTokens()
    assert service.verify(token, service.issue().verifier) is False


def test_invalid_verifier():
    service = SecureSessionTokens()
    issued = service.issue()
    for verifier in (b'', b'x' * 31, 'text', None):
        assert service.verify(issued.token, verifier) is False
