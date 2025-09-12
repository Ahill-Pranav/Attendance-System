class AttendanceModel:
    records = []  # {student_id, session_id, timestamp}

    @classmethod
    def mark_attendance(cls, student_id, session_id, timestamp):
        cls.records.append({
            "student_id": student_id,
            "session_id": session_id,
            "timestamp": timestamp
        })

    @classmethod
    def has_marked_attendance(cls, student_id, session_id):
        return any(r for r in cls.records if r["student_id"] == student_id and r["session_id"] == session_id)

    @classmethod
    def get_attendance_for_session(cls, session_id):
        return [r for r in cls.records if r["session_id"] == session_id]
