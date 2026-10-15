import cv2
import os

def register_employee(name):
    os.makedirs("employees", exist_ok=True)
    cam = cv2.VideoCapture("http://192.168.1.8:8080/video")
    print(f"[INFO] Press SPACE to capture photo for: {name}")

    while True:
        ret, frame = cam.read()
        cv2.imshow("Register - Press SPACE to capture", frame)
        key = cv2.waitKey(1)

        if key == 32:  # SPACE
            path = f"employees/{name}.jpg"
            cv2.imwrite(path, frame)
            print(f"[SAVED] {path}")
            break
        elif key == 27:  # ESC
            print("[CANCELLED]")
            break

    cam.release()
    cv2.destroyAllWindows()

# Usage:
register_employee("Muhammad Ali")