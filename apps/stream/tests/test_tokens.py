import pytest

from sml_stream.tokens import TokenError, sign, verify

SECRET = "test-stream-secret"
# Same golden vector as apps/api/sml/jobs/tests/test_streams.py.
GOLDEN_CLAIMS = {"sid": "s-1", "exp": 2000000000, "model": "skku-aigc", "max_seconds": 90.0}
GOLDEN_TOKEN = ("eyJleHAiOjIwMDAwMDAwMDAsIm1heF9zZWNvbmRzIjo5MC4wLCJtb2RlbCI6InNra3UtYWlnYyIsInNpZCI6InMtMSJ9"
                ".0c11f53e74bb1aab76c7e0118a21ae5a8df008b99dc895b98b4b332048f0e218")


def test_golden_token_from_the_api_verifies():
    assert verify(GOLDEN_TOKEN, SECRET, now=1_900_000_000) == GOLDEN_CLAIMS
    assert sign(GOLDEN_CLAIMS, SECRET) == GOLDEN_TOKEN


@pytest.mark.parametrize("token", [GOLDEN_TOKEN[:-1] + "0", "x" + GOLDEN_TOKEN, "garbage", ""])
def test_tampered_tokens_fail(token):
    with pytest.raises(TokenError):
        verify(token, SECRET, now=1_900_000_000)


def test_expired_and_unsigned_tokens_fail():
    with pytest.raises(TokenError, match="expired"):
        verify(GOLDEN_TOKEN, SECRET, now=2_000_000_001)
    with pytest.raises(TokenError):
        verify(GOLDEN_TOKEN, "", now=1)
