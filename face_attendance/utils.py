# utils.py
import os
import sqlite3
import pickle
import numpy as np
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")
ENCODINGS_PATH = os.path.join(DATA_DIR, "encodings.pickle")
DB_PATH = os.path.join(DATA_DIR, "attendance.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# DB helpers
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            image_path TEXT
        )
    """)
    conn.commit()
    conn.close()

# Encodings helpers
def load_encodings():
    if not os.path.exists(ENCODINGS_PATH):
        return {}  # name -> list of encodings (numpy arrays)
    with open(ENCODINGS_PATH, "rb") as f:
        data = pickle.load(f)
    # ensure arrays are numpy arrays
    for k, v in data.items():
        data[k] = [np.array(arr) for arr in v]
    return data

def save_encodings(encodings):
    # encodings: dict name -> list of numpy arrays
    # convert arrays to python lists (pickle handles numpy fine too, but keep)
    with open(ENCODINGS_PATH, "wb") as f:
        pickle.dump(encodings, f)

# Attendance record
def add_attendance(name, image_path=None):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    c.execute("INSERT INTO attendance (name, date, time, image_path) VALUES (?, ?, ?, ?)",
              (name, date, time, image_path))
    conn.commit()
    conn.close()

def query_attendance(limit=100, start_date=None, end_date=None, name=None):
    conn = get_db_connection()
    c = conn.cursor()
    q = "SELECT * FROM attendance WHERE 1=1"
    params = []
    if name:
        q += " AND name = ?"
        params.append(name)
    if start_date:
        q += " AND date >= ?"
        params.append(start_date)
    if end_date:
        q += " AND date <= ?"
        params.append(end_date)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    c.execute(q, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
