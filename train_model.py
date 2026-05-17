import cv2
import os
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "dataset")
TRAINER_DIR = os.path.join(BASE_DIR, "trainer")
TRAINER_PATH = os.path.join(TRAINER_DIR, "trainer.yml")

# Create recognizer
recognizer = cv2.face.LBPHFaceRecognizer_create()

# Face detector
detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def getImagesAndLabels(path):

    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        return [], []

    imagePaths = [os.path.join(path, f) for f in os.listdir(path)]

    faceSamples = []
    ids = []

    for imagePath in imagePaths:

        # Skip non-image files
        if not imagePath.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        try:
            PIL_img = Image.open(imagePath).convert('L')
        except:
            print("Skipping corrupted file:", imagePath)
            continue

        img_numpy = np.array(PIL_img, 'uint8')

        # Extract student ID from filename
        id = int(os.path.split(imagePath)[-1].split(".")[1])

        faces = detector.detectMultiScale(img_numpy)

        for (x, y, w, h) in faces:
            faceSamples.append(img_numpy[y:y+h, x:x+w])
            ids.append(id)

    return faceSamples, ids


print("\nTraining faces. Please wait...")

faces, ids = getImagesAndLabels(DATASET_PATH)

if len(faces) == 0:
    print(f"No training data found in {DATASET_PATH}. Register students first, then run training again.")
    exit()

recognizer.train(faces, np.array(ids))

# Create trainer folder if not exists
os.makedirs(TRAINER_DIR, exist_ok=True)

# Save trained model
recognizer.write(TRAINER_PATH)

print("Training completed successfully!")
print("Total faces trained:", len(set(ids)))
print(f"Model saved at: {TRAINER_PATH}")