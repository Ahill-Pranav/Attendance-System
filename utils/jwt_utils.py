# utils/jwt_utils.py
import jwt
from datetime import datetime, timedelta

# Keep one secret in one place; you can later move to config.py or env var
JWT_SECRET = "jwt_secret_please_change"
JWT_ALGO = "HS256"
QR_EXPIRY_SECONDS = 10  # token lifetime

def create_qr_token(session_id: int, class_id: str, faculty_id: int, ttl_seconds: int = QR_EXPIRY_SECONDS):
    """
    Create a signed JWT payload for a session. Contains:
      - session_id (int)
      - class_id (str)
      - faculty_id (int)
      - iat, exp
    """
    now = datetime.utcnow()
    payload = {
        "session_id": int(session_id),
        "class_id": class_id,
        "faculty_id": int(faculty_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp())
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    # pyjwt returns str in v2+
    return token

def verify_qr_token(token: str):
    """
    Returns decoded payload if valid, else raises jwt exceptions.
    """
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    return payload
