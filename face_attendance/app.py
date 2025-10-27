from flask import Flask, render_template, request, jsonify, send_file
import os
import csv
from datetime import datetime, timedelta
import face_recognition
import numpy as np

# === Setup base directory ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# === Create required folders ===
for folder in ["uploads", "data", "exports", "known_faces"]:
    os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)

ATTENDANCE_FILE = os.path.join(BASE_DIR, "data", "attendance.csv")
USER_ATTENDANCE_DIR = os.path.join(BASE_DIR, "data", "attendance_users")
os.makedirs(USER_ATTENDANCE_DIR, exist_ok=True)

# === Global cache for known faces ===
KNOWN_ENCODINGS = []
KNOWN_NAMES = []

# === Rate-limit logging per user to avoid spam ===
LAST_LOGGED = {}

def _load_known_faces():
    global KNOWN_ENCODINGS, KNOWN_NAMES
    KNOWN_ENCODINGS, KNOWN_NAMES = [], []
    known_faces_dir = os.path.join(BASE_DIR, "known_faces")
    for file in os.listdir(known_faces_dir):
        if file.lower().endswith((".jpg", ".jpeg", ".png")):
            name = os.path.splitext(file)[0]
            image_path = os.path.join(known_faces_dir, file)
            image = face_recognition.load_image_file(image_path)
            encs = face_recognition.face_encodings(image)
            if len(encs) > 0:
                KNOWN_ENCODINGS.append(encs[0])
                KNOWN_NAMES.append(name)
_load_known_faces()

# === Create attendance.csv if not exists ===
if not os.path.exists(ATTENDANCE_FILE):
    with open(ATTENDANCE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "date", "time", "image_path"])

def _already_logged_today(name, date_str):
    """Check if user already logged attendance today"""
    user_file = os.path.join(USER_ATTENDANCE_DIR, f"{name}.csv")
    if not os.path.exists(user_file):
        return False
    with open(user_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["name"] == name and row["date"] == date_str:
                return True
    return False

def _next_id(csv_path):
    """Return the next integer ID for the given CSV (1-based). Falls back to 1 if file missing/empty."""
    if not os.path.exists(csv_path):
        return 1
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            max_id = 0
            for row in reader:
                try:
                    rid = int(row.get("id", 0))
                    if rid > max_id:
                        max_id = rid
                except (ValueError, TypeError):
                    # Skip non-integer IDs
                    continue
            return max_id + 1
    except Exception:
        return 1

# === Routes ===
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/register", methods=["POST"])
def register_face():
    if "image" not in request.files or "name" not in request.form:
        return jsonify({"error": "Name and image required"}), 400

    name = request.form["name"].strip()
    file = request.files["image"]

    if not name or file.filename == "":
        return jsonify({"error": "Invalid name or file"}), 400

    image = face_recognition.load_image_file(file)
    encs = face_recognition.face_encodings(image)
    if len(encs) == 0:
        return jsonify({"error": "No face detected in uploaded image."}), 400

    save_path = os.path.join(BASE_DIR, "known_faces", f"{name}.jpg")
    file.stream.seek(0)
    file.save(save_path)

    KNOWN_ENCODINGS.append(encs[0])
    KNOWN_NAMES.append(name)

    return jsonify({"success": True, "message": f"Face registered for {name}."})

@app.route("/api/recognize", methods=["POST"])
def recognize_face():
    if "image" not in request.files:
        return jsonify({"success": False, "message": "No image uploaded."}), 400

    file = request.files["image"]
    test_image = face_recognition.load_image_file(file)
    face_locations = face_recognition.face_locations(test_image, model="hog")

    if len(face_locations) == 0:
        return jsonify({"success": False, "message": "No face detected."}), 400

    test_encodings = face_recognition.face_encodings(test_image, face_locations)
    detections = []

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    file_time = time.replace(":", "-")  # Safe for Windows filenames
    event_id_base = now.strftime("%Y%m%d-%H%M%S")

    for encoding, loc in zip(test_encodings, face_locations):
        name = "Unknown"
        if len(KNOWN_ENCODINGS) > 0:
            face_distances = face_recognition.face_distance(KNOWN_ENCODINGS, encoding)
            best_match = np.argmin(face_distances)
            if face_distances[best_match] < 0.6:
                name = KNOWN_NAMES[best_match]

        top, right, bottom, left = loc
        detections.append({"name": name, "top": top, "right": right, "bottom": bottom, "left": left})

        if name != "Unknown":
            # Per-user cooldown (e.g., 60s) to avoid logging every auto-scan
            last = LAST_LOGGED.get(name)
            if last and (now - last) < timedelta(seconds=60):
                continue
            img_path = os.path.join(BASE_DIR, "uploads", f"{name}_{date}_{file_time}.jpg")
            file.stream.seek(0)
            file.save(img_path)

            # Determine next numeric IDs
            global_next_id = _next_id(ATTENDANCE_FILE)
            user_file = os.path.join(USER_ATTENDANCE_DIR, f"{name}.csv")
            user_next_id = _next_id(user_file)

            with open(ATTENDANCE_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([global_next_id, name, date, time, img_path])

            new_file = not os.path.exists(user_file)
            with open(user_file, "a", newline="", encoding="utf-8") as uf:
                writer = csv.writer(uf)
                if new_file:
                    writer.writerow(["id", "name", "date", "time", "image_path"])
                writer.writerow([user_next_id, name, date, time, img_path])
            # Update last logged time
            LAST_LOGGED[name] = now

    return jsonify({"success": True, "detections": detections})

@app.route("/api/attendance", methods=["GET"])
def get_attendance():
    data = []
    if os.path.exists(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)
    return jsonify({"success": True, "attendance": data})

@app.route("/api/users", methods=["GET"])
def list_users():
    users = set()
    known_dir = os.path.join(BASE_DIR, "known_faces")
    if os.path.isdir(known_dir):
        for file in os.listdir(known_dir):
            if file.lower().endswith((".jpg", ".jpeg", ".png")):
                users.add(os.path.splitext(file)[0])
    if os.path.isdir(USER_ATTENDANCE_DIR):
        for file in os.listdir(USER_ATTENDANCE_DIR):
            if file.lower().endswith(".csv"):
                users.add(os.path.splitext(file)[0])
    return jsonify({"success": True, "users": sorted(users)})

@app.route("/api/attendance/<name>", methods=["GET"])
def get_user_attendance(name):
    user_file = os.path.join(USER_ATTENDANCE_DIR, f"{name}.csv")
    records = []
    if os.path.exists(user_file):
        with open(user_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            records = list(reader)
    return jsonify({"success": True, "attendance": records})

@app.route("/export", methods=["GET"])
def export_csv():
    if not os.path.exists(ATTENDANCE_FILE):
        return jsonify({"error": "No attendance data found."}), 404
    return send_file(ATTENDANCE_FILE, as_attachment=True)

@app.route("/logo.png", methods=["GET"])
def serve_logo():
    root_logo = os.path.join(os.path.dirname(BASE_DIR), "image.png")
    if os.path.exists(root_logo):
        return send_file(root_logo)
    # Fallback to static if user moves it there later
    static_logo = os.path.join(app.static_folder, "image.png")
    if os.path.exists(static_logo):
        return send_file(static_logo)
    return ("", 404)

if __name__ == "__main__":
    app.run(debug=False, port=5000)
