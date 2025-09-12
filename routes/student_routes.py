from flask import Blueprint, render_template, session, request, jsonify
from models.session_model import AttendanceSession, AttendanceRecord
from models import db
from datetime import datetime
import jwt

JWT_SECRET = "supersecretkey"
student_bp = Blueprint("student", __name__)

@student_bp.route("/")
def dashboard():
    if session.get("role") != "student":
        return "Unauthorized", 403
    return render_template("student.html")

@student_bp.route("/scan_qr", methods=["POST"])
def scan_qr():
    if session.get("role") != "student":
        return "Unauthorized", 403

    token = request.json.get("token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        session_id = AttendanceSession.query.filter_by(token=token).first()

        if session_id and session_id.expiry > datetime.utcnow():
            already = AttendanceRecord.query.filter_by(
                session_id=session_id.id, student_id=session["user_id"]
            ).first()
            if not already:
                record = AttendanceRecord(
                    session_id=session_id.id, student_id=session["user_id"]
                )
                db.session.add(record)
                db.session.commit()
            return jsonify({"status": "present", "faculty": session_id.faculty_id})
        else:
            return jsonify({"status": "expired"})
    except Exception:
        return jsonify({"status": "invalid"})
