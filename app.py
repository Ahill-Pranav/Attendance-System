# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import jwt, qrcode, io, base64, csv, sqlite3
from datetime import datetime, timedelta, date
import firebase_admin
from firebase_admin import credentials, auth
import os

# -------------------- Configuration --------------------
ROLE_MAPPING = {
    "shajanamirsha.ct23@bitsathy.ac.in": "faculty",
    "ahillpranav.ct23@bitsathy.ac.in": "student",
    "dharshini.ct23@bitsathy.ac.in": "student",
    "thanisha.ct23@bitsathy.ac.in": "student"
}

APP_SECRET = "secret123"
JWT_SECRET = "supersecretkey"
DB_FILE = "attendance.db"
FIREBASE_JSON = "smart-attendance-4e71f-firebase-adminsdk-fbsvc-cda0b1adc1.json"  # update if needed

app = Flask(__name__)
app.secret_key = APP_SECRET

# -------------------- Database helpers --------------------
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            student_name TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# -------------------- Firebase Admin init --------------------
if not os.path.exists(FIREBASE_JSON):
    print(f"Warning: Firebase service account JSON not found at '{FIREBASE_JSON}'. Google login will fail until fixed.")
else:
    cred = credentials.Certificate(FIREBASE_JSON)
    firebase_admin.initialize_app(cred)

# -------------------- Routes --------------------
@app.route('/')
def root():
    return redirect(url_for('login'))

# --- Login page (renders login.html) ---
@app.route('/login')
def login():
    return render_template('login.html')

# --- Google login endpoint (expects JSON {token: <idToken>}) ---
@app.route('/google_login', methods=['POST'])
def google_login():
    data = request.get_json() or {}
    token = data.get("token")
    if not token:
        return jsonify({"success": False, "msg": "No token provided"}), 400
    try:
        decoded_token = auth.verify_id_token(token)
        email = decoded_token.get("email")
        name = decoded_token.get("name", email)

        if email not in ROLE_MAPPING:
            return jsonify({"success": False, "msg": "Unauthorized email"}), 403

        role = ROLE_MAPPING[email]
        if role == "faculty":
            session["faculty"] = {"id": email, "name": name}
            redirect_url = url_for("faculty_dashboard")
        else:
            session["student"] = {"id": email, "name": name}
            redirect_url = url_for("student_dashboard")

        return jsonify({"success": True, "redirect": redirect_url})
    except Exception as e:
        print("Firebase verification failed:", e)
        return jsonify({"success": False, "msg": "Login failed"}), 400

# -------------------- Faculty --------------------
@app.route('/faculty_dashboard')
def faculty_dashboard():
    if 'faculty' not in session:
        return redirect(url_for('login'))
    return render_template('faculty.html')

@app.route('/generate_qr')
def generate_qr():
    if 'faculty' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    class_id = "CS101"  # you can make this dynamic per faculty/class
    expiry = datetime.utcnow() + timedelta(seconds=10)  # 10s validity
    payload = {"class_id": class_id, "exp": expiry}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # Create QR image (base64)
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return jsonify({"qr": qr_b64, "expires_in": 10})

@app.route('/attendance_list')
def attendance_list():
    if 'faculty' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    rows = conn.execute("SELECT student_id, student_name, timestamp FROM attendance ORDER BY timestamp DESC").fetchall()
    conn.close()
    students = [{"id": r["student_id"], "name": r["student_name"], "time": r["timestamp"]} for r in rows]
    return jsonify(students)

@app.route('/export_csv')
def export_csv():
    if 'faculty' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    rows = conn.execute("SELECT student_id, student_name, timestamp FROM attendance ORDER BY timestamp DESC").fetchall()
    conn.close()

    filename = f"CS101_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Student ID", "Name", "Timestamp"])
        for r in rows:
            writer.writerow([r["student_id"], r["student_name"], r["timestamp"]])

    # return the filename or offer for download
    return send_file(filename, as_attachment=True)

# -------------------- Student --------------------
@app.route('/student_dashboard')
def student_dashboard():
    if 'student' not in session:
        return redirect(url_for('login'))
    return render_template('student.html')

@app.route('/check_attendance')
def check_attendance():
    if 'student' not in session:
        return jsonify({"status": "Not Logged In"})
    student = session['student']
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM attendance WHERE student_id=? ORDER BY timestamp DESC LIMIT 1", (student["id"],)).fetchone()
    conn.close()
    return jsonify({"status": "Present" if row else "Absent"})

@app.route('/scan_qr', methods=['POST'])
def scan_qr():
    if 'student' not in session:
        return jsonify({"msg": "Not logged in"}), 401
    data = request.get_json() or {}
    token = data.get("token")
    if not token:
        return jsonify({"msg": "No token received"}), 400

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        class_id = payload.get("class_id")
        student = session['student']

        conn = get_db_connection()
        # check duplicate for same class
        row = conn.execute("SELECT * FROM attendance WHERE student_id=? AND class_id=?", (student["id"], class_id)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO attendance (class_id, student_id, student_name, timestamp) VALUES (?, ?, ?, ?)",
                (class_id, student["id"], student["name"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
        conn.close()
        return jsonify({"msg": "Attendance marked successfully!"})
    except jwt.ExpiredSignatureError:
        return jsonify({"msg": "QR Code expired!"})
    except Exception as e:
        print("scan_qr error:", e)
        return jsonify({"msg": "Invalid QR Code"})

# -------------------- Utility: logout --------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------- Run --------------------
if __name__ == '__main__':
    # bind to 0.0.0.0 if you want to access from mobile: app.run(debug=True, host='0.0.0.0')
    app.run(debug=True)
