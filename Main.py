import cv2
import mysql.connector
from datetime import date
import os
import sys
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

# DATABASE CONNECTION
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="smart_attendance"
)

cursor = db.cursor()
ensure_schema(db, cursor)

# LOAD TRAINED MODEL
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("trainer/trainer.yml")

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# CAMERA
cam = open_camera(0)
if cam is None:
    raise RuntimeError(
        "Unable to open the camera. On macOS, allow camera access for Terminal/Python from System Settings."
    )

# Students already marked today in this session
marked_students = set()

# Multi-frame recognition tracker
face_counter = {}
REQUIRED_FRAMES = 5

print("System Started...")
print("Press Q to quit\n")

while True:

    ret, frame = cam.read()
    if not ret or frame is None:
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(gray, 1.2, 6, minSize=(100,100))

    # Only allow recognition if exactly ONE face is visible
    if len(faces) != 1:
        cv2.imshow("Smart Attendance System", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        continue

    for (x, y, w, h) in faces:
        label = "Unknown"

        student_id, confidence = recognizer.predict(gray[y:y+h, x:x+w])

        if confidence < 50:

            # Increase detection count
            if student_id in face_counter:
                face_counter[student_id] += 1
            else:
                face_counter[student_id] = 1

            # Confirm recognition after several frames
            if face_counter[student_id] >= REQUIRED_FRAMES:

                cursor.execute(
                    "SELECT name FROM students WHERE student_id=%s",
                    (student_id,)
                )

                result = cursor.fetchone()

                if result:

                    name = result[0]
                    label = name

                    if student_id not in marked_students:

                        today = date.today()

                        cursor.execute(
                            "SELECT * FROM attendance WHERE student_id=%s AND date=%s",
                            (student_id, today)
                        )

                        record = cursor.fetchone()

                        if record is None:

                            cursor.execute(
                                "INSERT INTO attendance (student_id,date,status) VALUES (%s,%s,%s)",
                                (student_id, today, "Present")
                            )

                            db.commit()

                            print(f"Attendance Marked → {name}")

                        else:
                            print(f"{name} already marked today")

                        marked_students.add(student_id)

        else:
            label = "Unknown"

        # Draw rectangle
        cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)

        # Show name
        if confidence < 60:
            cv2.putText(
                frame,
                label,
                (x, y-10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0,255,0),
                2
            )
        else:
            cv2.putText(
                frame,
                "Unknown",
                (x, y-10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0,0,255),
                2
            )

    cv2.imshow("Smart Attendance System", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break


# EXIT
cam.release()
cv2.destroyAllWindows()
db.close()

print("\nExporting attendance to Excel...")

os.system("python export_attendance.py")

print("System Closed")