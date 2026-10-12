import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from app.core.config import get_settings

settings = get_settings()

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

def generate_tenant_api_key() -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32)
    prefix = f"apex_{token[:8]}"
    raw_key = f"{prefix}_{token[8:]}"

    salted_input = f"{raw_key}:{settings.API_KEY_SALT}"
    hashed_key = ph.hash(salted_input)

    return raw_key, prefix, hashed_key

def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    try:
        salted_input = f"{raw_key}:{settings.API_KEY_SALT}"
        return ph.verify(hashed_key, salted_input)
    except VerifyMismatchError:
        return False
    except Exception:
        return False
