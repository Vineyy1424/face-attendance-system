import os
import cv2
import time
import sys
import mysql.connector
from db_schema import ensure_schema


def open_camera(index=0):
    backends = [None]
    if sys.platform == "darwin":
        backends = [cv2.CAP_AVFOUNDATION, None]
    elif sys.platform.startswith("win"):
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]

    for backend in backends:
        cam = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
        if cam is not None and cam.isOpened():
            return cam
        if cam is not None:
            cam.release()

    return None

# Connect to MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="smart_attendance"
)

cursor = db.cursor()
ensure_schema(db, cursor)

# Take student details
name = input("Enter Name: ")
roll_no = input("Enter Roll Number: ")
birthdate = input("Enter Birthdate (YYYY-MM-DD): ")

# Insert into database
cursor.execute(
    "INSERT INTO students (name,roll_no,birthdate) VALUES (%s,%s,%s)",
    (name,roll_no,birthdate)
)

db.commit()

# Get generated student_id
student_id = cursor.lastrowid

print("Student Registered with ID:", student_id)

# Create dataset folder if not exists
if not os.path.exists("dataset"):
    os.makedirs("dataset")

# Start camera
cam = open_camera(0)
if cam is None:
    raise RuntimeError(
        "Unable to open the camera. On macOS, allow camera access for Terminal/Python from System Settings."
    )

import time
time.sleep(2)

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

count = 0

print("Look at the camera...")

while True:

    ret, img = cam.read()
    if not ret or img is None:
        continue

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    faces = face_detector.detectMultiScale(gray, 1.3, 5)

    for (x, y, w, h) in faces:

        count += 1

        cv2.imwrite(
            f"dataset/user.{student_id}.{count}.jpg",
            gray[y:y+h, x:x+w]
        )

        cv2.rectangle(img, (x, y), (x+w, y+h), (255, 0, 0), 2)

        cv2.imshow('Register Face', img)

        time.sleep(0.2)

    # Stop after 40 images
    if count >= 40:
        break

    # Press ESC to stop early
    if cv2.waitKey(1) == 27:
        break

print("Face Registered Successfully!")

cam.release()
cv2.destroyAllWindows()

# AUTO TRAIN MODEL 

os.system("python train_model.py")

print("Training completed successfully!")