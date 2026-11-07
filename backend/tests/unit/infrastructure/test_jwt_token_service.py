from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest

from app.application.ports.token_service import TokenType
from app.domain.errors import InvalidToken
from app.infrastructure.security.jwt_token_service import JwtTokenService
from tests.unit.application.fakes import MutableClock

SECRET = "test-secret-with-enough-length-for-hs256!"
ISSUED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock(ISSUED_AT)


@pytest.fixture
def service(clock: MutableClock) -> JwtTokenService:
    return JwtTokenService(
        secret=SECRET,
        access_ttl=timedelta(minutes=15),
        refresh_ttl=timedelta(days=7),
        clock=clock,
    )


def test_access_token_round_trip(service: JwtTokenService) -> None:
    user_id = uuid4()
    pair = service.issue_pair(user_id)

    assert service.decode(pair.access_token, TokenType.ACCESS) == user_id
    assert service.decode(pair.refresh_token, TokenType.REFRESH) == user_id


def test_claims_and_lifetimes(service: JwtTokenService) -> None:
    user_id = uuid4()
    pair = service.issue_pair(user_id)
    opts = {"verify_exp": False}

    access = jwt.decode(pair.access_token, SECRET, algorithms=["HS256"], options=opts)
    refresh = jwt.decode(pair.refresh_token, SECRET, algorithms=["HS256"], options=opts)

    assert access["sub"] == str(user_id)
    assert access["type"] == "access"
    assert access["exp"] - access["iat"] == 15 * 60
    assert refresh["type"] == "refresh"
    assert refresh["exp"] - refresh["iat"] == 7 * 24 * 3600
    assert UUID(access["jti"]) != UUID(refresh["jti"])


def test_refresh_token_cannot_be_used_as_access_token(service: JwtTokenService) -> None:
    pair = service.issue_pair(uuid4())

    with pytest.raises(InvalidToken):
        service.decode(pair.refresh_token, TokenType.ACCESS)


def test_access_token_cannot_be_used_as_refresh_token(service: JwtTokenService) -> None:
    pair = service.issue_pair(uuid4())

    with pytest.raises(InvalidToken):
        service.decode(pair.access_token, TokenType.REFRESH)


def test_expired_access_token_is_rejected(service: JwtTokenService, clock: MutableClock) -> None:
    pair = service.issue_pair(uuid4())
    clock.now = ISSUED_AT + timedelta(minutes=15, seconds=1)

    with pytest.raises(InvalidToken):
        service.decode(pair.access_token, TokenType.ACCESS)


def test_access_token_valid_just_before_expiry(
    service: JwtTokenService, clock: MutableClock
) -> None:
    user_id = uuid4()
    pair = service.issue_pair(user_id)
    clock.now = ISSUED_AT + timedelta(minutes=14, seconds=59)

    assert service.decode(pair.access_token, TokenType.ACCESS) == user_id


def test_expired_refresh_token_is_rejected(service: JwtTokenService, clock: MutableClock) -> None:
    pair = service.issue_pair(uuid4())
    clock.now = ISSUED_AT + timedelta(days=7, seconds=1)

    with pytest.raises(InvalidToken):
        service.decode(pair.refresh_token, TokenType.REFRESH)


def test_tampered_payload_is_rejected(service: JwtTokenService) -> None:
    header, _payload, signature = service.issue_pair(uuid4()).access_token.split(".")
    forged_payload = jwt.encode(
        {"sub": str(uuid4()), "type": "access"}, "other-secret-of-sufficient-length!!"
    ).split(".")[1]

    with pytest.raises(InvalidToken):
        service.decode(f"{header}.{forged_payload}.{signature}", TokenType.ACCESS)


def test_token_signed_with_other_secret_is_rejected(
    service: JwtTokenService, clock: MutableClock
) -> None:
    other = JwtTokenService(
        secret="a-completely-different-secret-value!!",
        access_ttl=timedelta(minutes=15),
        refresh_ttl=timedelta(days=7),
        clock=clock,
    )

    with pytest.raises(InvalidToken):
        service.decode(other.issue_pair(uuid4()).access_token, TokenType.ACCESS)


def test_alg_none_token_is_rejected(service: JwtTokenService) -> None:
    token = jwt.encode(
        {"sub": str(uuid4()), "type": "access", "exp": ISSUED_AT + timedelta(hours=1)},
        key=None,
        algorithm="none",
    )

    with pytest.raises(InvalidToken):
        service.decode(token, TokenType.ACCESS)


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "access"},  # no sub
        {"sub": "not-a-uuid", "type": "access"},
        {"sub": str(uuid4())},  # no type
    ],
)
def test_malformed_claims_are_rejected(service: JwtTokenService, payload: dict[str, str]) -> None:
    token = jwt.encode({**payload, "exp": ISSUED_AT + timedelta(hours=1)}, SECRET)

    with pytest.raises(InvalidToken):
        service.decode(token, TokenType.ACCESS)


def test_garbage_is_rejected(service: JwtTokenService) -> None:
    with pytest.raises(InvalidToken):
        service.decode("not.a.jwt", TokenType.ACCESS)


# --- refresh claims and rotation ------------------------------------------------


def test_decode_refresh_returns_session_claims(service: JwtTokenService) -> None:
    user_id = uuid4()
    pair = service.issue_pair(user_id)

    claims = service.decode_refresh(pair.refresh_token)

    raw = jwt.decode(
        pair.refresh_token, SECRET, algorithms=["HS256"], options={"verify_exp": False}
    )
    assert claims.user_id == user_id
    assert claims.token_id == raw["jti"]
    assert claims.session_id == raw["sid"]
    assert claims.expires_at == ISSUED_AT + timedelta(days=7)


def test_each_login_starts_a_new_session(service: JwtTokenService) -> None:
    user_id = uuid4()

    first = service.decode_refresh(service.issue_pair(user_id).refresh_token)
    second = service.decode_refresh(service.issue_pair(user_id).refresh_token)

    assert first.session_id != second.session_id


def test_rotation_keeps_session_and_original_expiry(
    service: JwtTokenService, clock: MutableClock
) -> None:
    user_id = uuid4()
    original = service.decode_refresh(service.issue_pair(user_id).refresh_token)
    clock.now = ISSUED_AT + timedelta(days=3)

    rotated_pair = service.rotate(original)
    rotated = service.decode_refresh(rotated_pair.refresh_token)

    assert rotated.user_id == user_id
    assert rotated.session_id == original.session_id
    assert rotated.expires_at == original.expires_at  # never extended past the login's TTL
    assert rotated.token_id != original.token_id
    assert service.decode(rotated_pair.access_token, TokenType.ACCESS) == user_id


def test_decode_refresh_rejects_access_tokens(service: JwtTokenService) -> None:
    with pytest.raises(InvalidToken):
        service.decode_refresh(service.issue_pair(uuid4()).access_token)


def test_decode_refresh_rejects_expired_tokens(
    service: JwtTokenService, clock: MutableClock
) -> None:
    pair = service.issue_pair(uuid4())
    clock.now = ISSUED_AT + timedelta(days=7)

    with pytest.raises(InvalidToken):
        service.decode_refresh(pair.refresh_token)


@pytest.mark.parametrize("missing", ["jti", "sid"])
def test_decode_refresh_requires_token_and_session_ids(
    service: JwtTokenService, missing: str
) -> None:
    claims = {
        "sub": str(uuid4()),
        "type": "refresh",
        "exp": ISSUED_AT + timedelta(days=1),
        "jti": "j",
        "sid": "s",
    }
    del claims[missing]

    with pytest.raises(InvalidToken):
        service.decode_refresh(jwt.encode(claims, SECRET))
