from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Twilio
from twilio.rest import Client

# AI Modules
from vehicle_detection import detect_congestion
from accident_detection import detect_accident
from congestion_prediction import predict_congestion
from rl_agent import route_decision
#voice
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = "traffic_secret"

socketio = SocketIO(app, cors_allowed_origins="*")

# GLOBAL STATE (controlled by admin)
traffic_state = {
    "congestion": "LOW",
    "accident": False,
    "vehicle_count": 10
}

# NORMAL ANALYZE API (fallback)

# 🚀 WEBSOCKET CONNECT
@socketio.on('connect')
def handle_connect():
    emit('update', traffic_state)

# 🚨 ADMIN TRIGGER
@app.route("/admin/update", methods=["POST"])
def admin_update():
    global traffic_state

    traffic_state = {
        "congestion": request.json.get("congestion"),
        "accident": request.json.get("accident"),
        "vehicle_count": request.json.get("vehicle_count")
    }

    # 🔥 PUSH TO ALL CLIENTS
    socketio.emit("update", traffic_state)

    return {"status": "updated"}
#------------------------------


DATABASE = "users.db"

# ---------------- TWILIO CONFIG ----------------

twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT,
            phone TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS traffic_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            congestion TEXT,
            vehicle_count INTEGER
        )
        """)

init_db()

# ---------------- SMS ALERT ----------------

def send_sms_alert(phone, message):

    try:

        if not phone:
            print("❌ No phone number found")
            return

        phone = str(phone).strip()

        # remove spaces
        phone = phone.replace(" ", "")

        # validate
        if not phone.startswith("+91"):
            if len(phone) == 10:
                phone = "+91" + phone
            else:
                print("❌ Invalid phone number:", phone)
                return

        if len(phone) != 13:
            print("❌ Invalid phone number:", phone)
            return

        print("📞 Sending SMS to:", phone)

        msg = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=phone
        )

        print("✅ SMS sent:", msg.sid)

    except Exception as e:
        print("❌ Twilio Error:", e)

# ---------------- AUTH ROUTES ----------------

@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/signup-page")
def signup_page():
    return render_template("signup.html")

@app.route("/signup", methods=["POST"])
def signup():

    username = request.form.get("username")
    password = request.form.get("password")
    phone = request.form.get("phone")

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users(username,password,phone) VALUES(?,?,?)",
                (username, password, phone)
            )
        return redirect("/?signup=success")

    except:
        return redirect("/signup-page")

@app.route("/login", methods=["POST"])
def login():

    username = request.form.get("username")
    password = request.form.get("password")

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()

    if user:
        session["user"] = username
        return redirect("/index")

    return "Invalid Login"

@app.route("/index")
def index():
    if "user" not in session:
        return redirect("/")
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/analysis-result")
def analysis_result():
    if "user" not in session:
        return redirect("/")
    return render_template("analysis_result.html")

@app.route("/traffic-analytics")
def traffic_analytics():
    if "user" not in session:
        return redirect("/")
    return render_template("analytics.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

# ---------------- TEST SMS ----------------

@app.route("/test-user-sms")
def test_user_sms():

    with get_db() as conn:
        row = conn.execute(
            "SELECT phone FROM users WHERE username=?",
            (session["user"],)
        ).fetchone()

    if row:
        send_sms_alert(row["phone"], "🚀 Test SMS from Smart Traffic System")

    return "SMS sent"

# ---------------- TRAFFIC ANALYSIS ----------------

traffic_history = []

@app.route("/analyze", methods=["POST"])
def analyze():

    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    video = "traffic.mp4"

    congestion = detect_congestion(video)

    vehicle_count = 10 if congestion=="LOW" else 25 if congestion=="MEDIUM" else 50
    
    accident = detect_accident(video)

    route = route_decision(congestion)

    suggestion = "Normal Route Recommended"

    traffic_history.append(vehicle_count)

    if len(traffic_history) > 10:
        traffic_history.pop(0)

    prediction_word = "NONE"

    if len(traffic_history) == 10:

        prediction_value = predict_congestion(traffic_history)

        if prediction_value < 20:
            prediction_word = "LOW"
        elif prediction_value < 40:
            prediction_word = "MEDIUM"
        else:
            prediction_word = "HIGH"
            suggestion = "Alternate Route Recommended"

    user_email = None
    user_phone = 6382939376

    with get_db() as conn:

        conn.execute(
            "INSERT INTO traffic_logs(time, congestion, vehicle_count) VALUES(?,?,?)",
            (str(datetime.datetime.now()), congestion, vehicle_count)
        )

        row = conn.execute(
            "SELECT email,phone FROM users WHERE username=?",
            (session["user"],)
        ).fetchone()

        if row:
            user_email = row["email"]
            user_phone = row["phone"]

    # ---------------- TRAFFIC ALERT ----------------
    if congestion == "HIGH":
        line1 = "Heavy traffic detected."
        line2 = "Alternate route suggested."

    elif congestion == "MEDIUM":
        line1 = "Moderate traffic detected."
        line2 = "Expect delays. Plan accordingly."

    else:
        line1 = "Traffic is smooth."
        line2 = "No alternate route needed."

    alert_message = f"""🚨 TRAFFIC ALERT 🚨
{line1}
{line2}
Drive safely and plan ahead.
"""

    if congestion in ["MEDIUM", "HIGH"]:

        print("🚀 Sending traffic alerts...")

        if user_phone:
            send_sms_alert(user_phone, alert_message)

    else:
        print("ℹ️ No traffic alert")

    # ---------------- ACCIDENT ALERT (FIXED) ----------------
    if accident:

        accident_message = """🚨 ACCIDENT ALERT 🚨
An accident has been detected on your route.
⚠️ Expect heavy delays.
🚧 Please take an alternate route immediately.
Drive safely.
"""

        print("🚨 Sending accident alert...")

        if user_phone:
            send_sms_alert(user_phone, accident_message)

    else:
        print("ℹ️ No accident detected")

    # ---------------- FINAL RESPONSE ----------------
    # 🔥 SEND REAL-TIME UPDATE TO DASHBOARD
    socketio.emit("update", {
        "congestion": congestion,
        "vehicle_count": vehicle_count,
        "accident": accident
    })
    return jsonify({
        "congestion": congestion,
        "vehicle_count": vehicle_count,
        "prediction": prediction_word,
        "suggestion": suggestion,
        "accident": accident 
    })
        
# ---------------- ANALYTICS ----------------

@app.route("/analytics")
def analytics():

    with get_db() as conn:
        data = conn.execute(
            "SELECT time,vehicle_count FROM traffic_logs ORDER BY id DESC LIMIT 20"
        ).fetchall()

    times = [row["time"][-8:] for row in reversed(data)]
    counts = [row["vehicle_count"] for row in reversed(data)]

    return jsonify({
        "times": times,
        "counts": counts
    })

# ---------------- RUN ----------------
@app.route("/fix-phone")
def fix_phone():

    with get_db() as conn:
        conn.execute("""
        UPDATE users
        SET phone='9876543210'
        WHERE phone='123456789'
        """)

    return "Phone updated"

@app.route("/show-users")
def show_users():

    with get_db() as conn:
        rows = conn.execute(
            "SELECT username, phone FROM users"
        ).fetchall()

    result = ""

    for row in rows:
        result += f"{row['username']} : {row['phone']}<br>"

    return result

if __name__ == "__main__":
    socketio.run(app, debug=True)