import qrcode, io, base64
import jwt
from datetime import datetime, timedelta

JWT_SECRET = "supersecretkey"

def generate_qr_token(class_id, faculty_id):
    expiry = datetime.utcnow() + timedelta(seconds=10)
    payload = {"class_id": class_id, "faculty_id": faculty_id, "exp": expiry}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return token, expiry
