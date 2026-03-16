import cv2
import os
import numpy as np
from PIL import Image

# Path of dataset
dataset_path = "dataset"

# Create recognizer
recognizer = cv2.face.LBPHFaceRecognizer_create()

# Face detector
detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def getImagesAndLabels(path):

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

faces, ids = getImagesAndLabels(dataset_path)

if len(faces) == 0:
    print("No training data found!")
    exit()

recognizer.train(faces, np.array(ids))

# Create trainer folder if not exists
if not os.path.exists("trainer"):
    os.makedirs("trainer")

# Save trained model
recognizer.write("trainer/trainer.yml")

print("Training completed successfully!")
print("Total faces trained:", len(set(ids)))
print("Model saved at: trainer/trainer.yml")