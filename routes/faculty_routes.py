from flask import Blueprint, render_template, session, jsonify
from utils.qr_utils import generate_qr_token
from models.session_model import AttendanceSession, AttendanceRecord
from models import db
from datetime import datetime

faculty_bp = Blueprint("faculty", __name__)

@faculty_bp.route("/")
def dashboard():
    if session.get("role") != "faculty":
        return "Unauthorized", 403
    return render_template("faculty.html")

@faculty_bp.route("/generate_qr")
def generate_qr():
    if session.get("role") != "faculty":
        return "Unauthorized", 403

    class_id = "CS101"
    token, expiry = generate_qr_token(class_id, session["user_id"])

    new_session = AttendanceSession(
        class_id=class_id, faculty_id=session["user_id"], token=token, expiry=expiry
    )
    db.session.add(new_session)
    db.session.commit()

    return jsonify({"token": token, "expires_at": expiry.isoformat()})

@faculty_bp.route("/attendance_list")
def attendance_list():
    if session.get("role") != "faculty":
        return "Unauthorized", 403

    sessions = AttendanceSession.query.filter_by(faculty_id=session["user_id"]).all()
    records = AttendanceRecord.query.all()

    result = []
    for r in records:
        student_info = {"id": r.student_id, "time": r.timestamp.strftime("%H:%M:%S")}
        result.append(student_info)

    return jsonify(result)
