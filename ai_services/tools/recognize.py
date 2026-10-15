import os
from deepface import DeepFace

DB_PATH = "employees/"

# ── PUT YOUR PHOTO PATH HERE ──────────────────────────
IMG_PATH =  "photo.jpg" 
# ─────────────────────────────────────────────────────

MATCH_THRESHOLD     = 0.35
UNCERTAIN_THRESHOLD = 0.50


def get_confidence(distance):
    return max(0, round((1 - distance) * 100, 1))


def recognize(img_path):
    if not os.path.exists(img_path):
        print(f"[ERROR] File not found: {img_path}")
        return

    print(f"[INFO] Checking: {img_path}")

    try:
        result = DeepFace.find(
            img_path=img_path,
            db_path=DB_PATH,
            model_name="Facenet512",
            detector_backend="retinaface",
            enforce_detection=False,
            silent=True
        )

        if result and len(result[0]) > 0:
            match      = result[0].iloc[0]
            distance   = match["distance"]
            name       = os.path.splitext(os.path.basename(match["identity"]))[0]
            confidence = get_confidence(distance)

            print(f"[DEBUG] Closest   : {name}")
            print(f"[DEBUG] Distance  : {round(distance, 4)}")
            print(f"[DEBUG] Confidence: {confidence}%")

            if distance < MATCH_THRESHOLD:
                print(f"[MATCH] ✅ {name} ({confidence}% confidence)")
            elif distance < UNCERTAIN_THRESHOLD:
                print(f"[UNCERTAIN] ⚠️  Might be {name} ({confidence}%)")
            else:
                print(f"[UNKNOWN] ❌ Not in database")
        else:
            print("[UNKNOWN] ❌ No face detected")

    except Exception as e:
        print(f"[ERROR] {e}")


recognize(IMG_PATH)