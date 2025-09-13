# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import jwt, qrcode, io, base64, csv, sqlite3
from datetime import datetime, timedelta, date
import os

# -------------------- Firebase Admin (optional) --------------------
FIREBASE_JSON = "smart-attendance-4e71f-firebase-adminsdk-fbsvc-cda0b1adc1.json"

FIREBASE_AVAILABLE = False
try:
    import firebase_admin
    from firebase_admin import credentials, auth as firebase_auth
    if os.path.exists(FIREBASE_JSON):
        cred = credentials.Certificate(FIREBASE_JSON)
        firebase_admin.initialize_app(cred)
        FIREBASE_AVAILABLE = True
        print("Firebase admin initialized using", FIREBASE_JSON)
    else:
        print(f"Firebase JSON not found at '{FIREBASE_JSON}'. Google sign-in (Firebase) will be disabled until provided.")
except Exception as e:
    print("firebase_admin import/init error:", e)
    FIREBASE_AVAILABLE = False

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

app = Flask(__name__)
app.secret_key = APP_SECRET

# -------------------- Database helpers & migration --------------------
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _table_columns(conn, table_name):
    cur = conn.execute(f"PRAGMA table_info('{table_name}')")
    return [r["name"] for r in cur.fetchall()]

def init_db():
    """
    Create attendance table if missing and add any missing columns.
    This migration is safe to run repeatedly.
    """
    conn = get_db_connection()
    c = conn.cursor()

    # Create table if it does not exist (legacy schema may have fewer columns).
    # We create with minimal columns that older code used to have, then migrate.
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

    # Now inspect columns and add missing ones we expect.
    existing_cols = _table_columns(conn, "attendance")
    expected_cols = {
        "faculty_id": "TEXT",
        "hour_index": "INTEGER"
    }

    for col, col_type in expected_cols.items():
        if col not in existing_cols:
            # Add column with a sensible default:
            # * faculty_id -> 'FacultyUnknown'
            # * hour_index -> 0 (I Hour)  — adjust manually later if you prefer a different mapping
            default_val = "'FacultyUnknown'" if col == "faculty_id" else "0"
            alter_sql = f"ALTER TABLE attendance ADD COLUMN {col} {col_type} DEFAULT {default_val}"
            print("Migrating DB: executing:", alter_sql)
            c.execute(alter_sql)
            conn.commit()

    conn.close()

# initialize (and migrate) DB on startup
init_db()

# -------------------- Routes --------------------
@app.route('/')
def root():
    return redirect(url_for('login'))

# Login page (email fallback + Firebase sign-in button in template)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email in ROLE_MAPPING:
            role = ROLE_MAPPING[email]
            if role == 'faculty':
                session['faculty'] = {'id': email, 'name': email}
                return redirect(url_for('faculty_dashboard'))
            else:
                session['student'] = {'id': email, 'name': email}
                return redirect(url_for('student_dashboard'))
        else:
            return render_template('login.html', error="Unauthorized email (use ROLE_MAPPING)", firebase_available=FIREBASE_AVAILABLE)

    return render_template('login.html', error=None, firebase_available=FIREBASE_AVAILABLE)

# Google/Firebase login endpoint (client sends Firebase ID token)
@app.route('/google_login', methods=['POST'])
def google_login():
    if not FIREBASE_AVAILABLE:
        return jsonify({"success": False, "msg": "Server Firebase not configured. Place service account JSON and restart."}), 500

    data = request.get_json(silent=True) or {}
    id_token = data.get("token")
    if not id_token:
        return jsonify({"success": False, "msg": "No ID token provided."}), 400

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        email = decoded_token.get("email")
        name = decoded_token.get("name", email)

        if not email:
            return jsonify({"success": False, "msg": "Email not found in token."}), 400

        if email not in ROLE_MAPPING:
            return jsonify({"success": False, "msg": "Unauthorized email."}), 403

        role = ROLE_MAPPING[email]
        if role == "faculty":
            session["faculty"] = {"id": email, "name": name}
            redirect_url = url_for("faculty_dashboard")
        else:
            session["student"] = {"id": email, "name": name}
            redirect_url = url_for("student_dashboard")

        return jsonify({"success": True, "redirect": redirect_url})
    except Exception as e:
        print("firebase verify error:", e)
        return jsonify({"success": False, "msg": "Token verification failed."}), 400

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------- Faculty --------------------
@app.route('/faculty_dashboard')
def faculty_dashboard():
    if 'faculty' not in session:
        return redirect(url_for('login'))
    return render_template('faculty.html', today=date.today().isoformat())

@app.route('/generate_qr')
def generate_qr():
    if 'faculty' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    class_id = request.args.get('class_id', 'CS101')
    faculty_id = session['faculty']['id']
    expiry = datetime.utcnow() + timedelta(seconds=10)
    payload = {"class_id": class_id, "faculty_id": faculty_id, "exp": expiry}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return jsonify({"qr": qr_b64, "expires_in": 10})

@app.route('/faculty_attendance')
def faculty_attendance():
    if 'faculty' not in session:
        return jsonify({"attendance": []})

    faculty = session['faculty']
    selected_date = request.args.get('date') or date.today().isoformat()

    conn = get_db_connection()
    # It's safe now to query hour_index & faculty_id (migration created them if missing)
    rows = conn.execute(
        "SELECT student_id, student_name, hour_index, timestamp FROM attendance WHERE faculty_id=? AND date(timestamp)=? ORDER BY hour_index ASC",
        (faculty['id'], selected_date)
    ).fetchall()
    conn.close()

    hours = {i: [] for i in range(7)}
    for r in rows:
        hours[r['hour_index']].append({
            "student_id": r["student_id"],
            "student_name": r["student_name"],
            "timestamp": r["timestamp"]
        })

    periods = ["I Hour","II Hour","III Hour","IV Hour","V Hour","VI Hour","VII Hour"]
    response = []
    for i in range(7):
        response.append({
            "hour": periods[i],
            "students": hours[i]
        })

    return jsonify({"date": selected_date, "hours": response})

@app.route('/export_csv')
def export_csv():
    if 'faculty' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    rows = conn.execute("SELECT class_id, student_id, student_name, faculty_id, hour_index, timestamp FROM attendance ORDER BY timestamp DESC").fetchall()
    conn.close()

    filename = f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Class ID", "Student ID", "Student Name", "Faculty ID", "Hour Index", "Timestamp"])
        for r in rows:
            writer.writerow([r["class_id"], r["student_id"], r["student_name"], r["faculty_id"], r["hour_index"], r["timestamp"]])
    return send_file(filename, as_attachment=True)

# -------------------- Student --------------------
@app.route('/student_dashboard')
def student_dashboard():
    if 'student' not in session:
        return redirect(url_for('login'))
    return render_template('student.html', today=date.today().isoformat())

@app.route('/check_attendance')
def check_attendance():
    if 'student' not in session:
        return jsonify({"status": "Not Logged In"})
    student = session['student']
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM attendance WHERE student_id=? ORDER BY timestamp DESC LIMIT 1", (student['id'],)).fetchone()
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
        faculty_id = payload.get("faculty_id", "FacultyUnknown")
        student = session['student']

        today_str = datetime.now().strftime("%Y-%m-%d")
        conn = get_db_connection()
        rows = conn.execute("SELECT COUNT(*) as c FROM attendance WHERE student_id=? AND date(timestamp)=?", (student['id'], today_str)).fetchone()
        present_count = rows['c']
        if present_count >= 7:
            conn.close()
            return jsonify({"msg": "All 7 hours already marked", "success": False})

        hour_index = present_count
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO attendance (class_id, student_id, student_name, faculty_id, hour_index, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (class_id, student['id'], student['name'], faculty_id, hour_index, timestamp)
        )
        conn.commit()
        conn.close()

        periods = ["I","II","III","IV","V","VI","VII"]
        return jsonify({"msg": "Attendance marked", "success": True, "hour": periods[hour_index], "hour_index": hour_index, "timestamp": timestamp})
    except jwt.ExpiredSignatureError:
        return jsonify({"msg": "QR Code expired!", "success": False})
    except Exception as e:
        print("scan_qr error:", e)
        return jsonify({"msg": "Invalid QR Code", "success": False})

@app.route('/student_attendance')
def student_attendance():
    if 'student' not in session:
        return jsonify({"hours": []})

    student = session['student']
    selected_date = request.args.get('date') or date.today().isoformat()

    conn = get_db_connection()
    rows = conn.execute("SELECT class_id, hour_index, timestamp, faculty_id FROM attendance WHERE student_id=? AND date(timestamp)=? ORDER BY hour_index ASC", (student['id'], selected_date)).fetchall()
    conn.close()

    record_map = {r['hour_index']: r for r in rows}

    periods = ["I Hour","II Hour","III Hour","IV Hour","V Hour","VI Hour","VII Hour"]
    res = []
    for i in range(7):
        r = record_map.get(i)
        if r:
            res.append({
                "hour": periods[i],
                "class_id": r["class_id"],
                "status": "Present",
                "timestamp": r["timestamp"],
                "faculty": r["faculty_id"]
            })
        else:
            res.append({
                "hour": periods[i],
                "class_id": "-",
                "status": "Absent",
                "timestamp": "-",
                "faculty": "-"
            })
    return jsonify({"date": selected_date, "hours": res})

# -------------------- Run --------------------
if __name__ == '__main__':
    app.run(debug=True)
