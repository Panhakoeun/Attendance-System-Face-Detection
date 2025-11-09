from flask import Flask, render_template, request, jsonify, send_file, url_for, send_from_directory
import os
import csv
from datetime import datetime, timedelta
import face_recognition
import numpy as np
from werkzeug.utils import secure_filename

# === Setup base directory ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    try:
        return render_template("index.html")
    except Exception as e:
        return f"Error loading template: {str(e)}"

# Serve static files
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# Serve logo - consolidated route
@app.route('/logo.png')
def serve_logo():
    # First try the root directory
    root_logo = os.path.join(os.path.dirname(BASE_DIR), "logo.png")
    if os.path.exists(root_logo):
        return send_file(root_logo)
    # Then try the static folder
    return send_from_directory('static', 'logo.png')

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
    unknown_face_encodings = []
    unknown_face_locations = []

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    file_time = time.replace(":", "-")
    event_id_base = now.strftime("%Y%m%d-%H%M%S")

    for i, (encoding, loc) in enumerate(zip(test_encodings, face_locations)):
        name = None
        confidence = 1.0
        
        if len(KNOWN_ENCODINGS) > 0:
            face_distances = face_recognition.face_distance(KNOWN_ENCODINGS, encoding)
            best_match = np.argmin(face_distances)
            confidence = face_distances[best_match]
            if confidence < 0.6:  # Lower is better match
                name = KNOWN_NAMES[best_match]
        
        top, right, bottom, left = loc
        
        if name is None:
            # Store unknown face data for potential registration
            unknown_face_encodings.append(encoding.tolist())  # Convert numpy array to list for JSON
            unknown_face_locations.append(loc)
            detections.append({
                "status": "unknown",
                "face_id": len(unknown_face_encodings) - 1,
                "top": top, 
                "right": right, 
                "bottom": bottom, 
                "left": left
            })
        else:
            # Handle known face
            detections.append({
                "status": "recognized",
                "name": name,
                "confidence": float(1 - confidence),  # Convert to 0-1 scale where 1 is best
                "top": top, 
                "right": right, 
                "bottom": bottom, 
                "left": left
            })
            
            # Log attendance for known faces
            last = LAST_LOGGED.get(name)
            if last and (now - last) < timedelta(seconds=60):
                continue
                
            img_path = os.path.join(BASE_DIR, "uploads", f"{name}_{date}_{file_time}.jpg")
            file.stream.seek(0)
            file.save(img_path)

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
                
            LAST_LOGGED[name] = now

    response = {
        "success": True, 
        "detections": detections
    }
    
    # Add unknown face data if any were found
    if unknown_face_encodings:
        response["unknown_faces"] = {
            "encodings": unknown_face_encodings,
            "locations": [{"top": t, "right": r, "bottom": b, "left": l} 
                         for (t, r, b, l) in unknown_face_locations]
        }
    
    return jsonify(response)

@app.route("/api/register_unknown", methods=["POST"])
def register_unknown_face():
    try:
        if not request.is_json:
            return jsonify({"success": False, "message": "Missing JSON in request"}), 400
            
        data = request.get_json()
        
        if not all(key in data for key in ["name", "face_index", "encodings"]):
            return jsonify({"success": False, "message": "Name, face index, and encodings are required"}), 400
        
        name = data["name"].strip()
        face_index = data["face_index"]
        encodings = data["encodings"]
        
        if not name or face_index < 0 or face_index >= len(encodings):
            return jsonify({"success": False, "message": "Invalid name or face index"}), 400
        
        # Get the face encoding
        try:
            encoding = np.array(encodings[face_index])
            
            # Save the face image (we'll use the first available face from the last recognition)
            known_faces_dir = os.path.join(BASE_DIR, "known_faces")
            os.makedirs(known_faces_dir, exist_ok=True)
            
            # Generate a unique filename
            base_filename = f"{name}.jpg"
            counter = 1
            while os.path.exists(os.path.join(known_faces_dir, base_filename)):
                base_filename = f"{name}_{counter}.jpg"
                counter += 1
                
            save_path = os.path.join(known_faces_dir, base_filename)
            
            # Try to get the face image from the last recognition
            if hasattr(recognize_face, 'last_unknown_face_image'):
                face_image = recognize_face.last_unknown_face_image
                if face_image is not None:
                    import cv2
                    cv2.imwrite(save_path, cv2.cvtColor(face_image, cv2.COLOR_RGB2BGR))
            
            # Add to known faces
            KNOWN_ENCODINGS.append(encoding)
            KNOWN_NAMES.append(name)
            
            # Save the updated encodings to disk
            np.save(os.path.join(BASE_DIR, "known_encodings.npy"), {"encodings": KNOWN_ENCODINGS, "names": KNOWN_NAMES})
            
            return jsonify({
                "success": True, 
                "message": f"Successfully registered {name}.",
                "name": name
            })
            
        except Exception as e:
            return jsonify({"success": False, "message": f"Error processing face data: {str(e)}"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

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


if __name__ == "__main__":
    app.run(debug=False, port=5000)
