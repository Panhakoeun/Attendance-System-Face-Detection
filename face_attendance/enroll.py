# enroll.py
import os
import face_recognition
from PIL import Image
import numpy as np
from utils import load_encodings, save_encodings, UPLOAD_DIR

def enroll_image(image_path, name):
    # Load image
    image = face_recognition.load_image_file(image_path)
    # detect face encodings
    encs = face_recognition.face_encodings(image)
    if len(encs) == 0:
        return False, "No face found in image."
    # Use first face (if multiple, you can extend)
    encoding = encs[0]
    # load existing encodings
    encodings = load_encodings()
    encodings.setdefault(name, []).append(encoding)
    save_encodings(encodings)
    return True, f"Enrolled {name} with {len(encodings[name])} encodings"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    ok, msg = enroll_image(args.image, args.name)
    print(msg)
