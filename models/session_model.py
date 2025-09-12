from models import db
from datetime import datetime

class AttendanceSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(20), nullable=False)
    faculty_id = db.Column(db.Integer, nullable=False)
    token = db.Column(db.String(500), nullable=False)
    expiry = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_session.id"))
    student_id = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
