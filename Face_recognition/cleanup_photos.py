"""
Cleanup script: Keeps only the best 5 photos per employee.
Scores images by face size and clarity using OpenCV face detection.
"""
import os
import cv2
import sys

EMPLOYEES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employees')
KEEP_COUNT = 5

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def score_image(img_path):
    """Score an image by face size and sharpness. Higher = better."""
    img = cv2.imread(img_path)
    if img is None:
        return -1
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5)
    
    if len(faces) == 0:
        # No face detected — low score but don't discard completely
        return 0
    
    # Use the largest face found
    areas = [w * h for (x, y, w, h) in faces]
    max_area = max(areas)
    
    # Also factor in image sharpness (Laplacian variance)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Combined score: face area (most important) + sharpness bonus
    return max_area + (sharpness * 0.1)

def main():
    print(f"\n{'='*60}")
    print(f"  PHOTO CLEANUP — Keeping best {KEEP_COUNT} per employee")
    print(f"{'='*60}\n")
    
    total_deleted = 0
    total_kept = 0
    
    for folder_name in sorted(os.listdir(EMPLOYEES_DIR)):
        folder_path = os.path.join(EMPLOYEES_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue
        
        # Get all image files
        images = []
        for f in os.listdir(folder_path):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = os.path.join(folder_path, f)
                images.append(full_path)
        
        if len(images) <= KEEP_COUNT:
            print(f"  [OK] {folder_name}: {len(images)} images (no cleanup needed)")
            total_kept += len(images)
            continue
        
        # Score each image
        scored = []
        for img_path in images:
            score = score_image(img_path)
            scored.append((img_path, score))
        
        # Sort by score (highest first) and keep top N
        scored.sort(key=lambda x: x[1], reverse=True)
        
        keep = scored[:KEEP_COUNT]
        delete = scored[KEEP_COUNT:]
        
        print(f"\n  [FOLDER] {folder_name} ({len(images)} images -> keeping {KEEP_COUNT}):")
        print(f"     KEEPING:")
        for path, score in keep:
            print(f"       [OK] {os.path.basename(path)} (score: {score:.0f})")
        
        print(f"     DELETING:")
        for path, score in delete:
            print(f"       [DEL] {os.path.basename(path)} (score: {score:.0f})")
            os.remove(path)
            total_deleted += 1
        
        total_kept += KEEP_COUNT
    
    # Delete .pkl cache so it rebuilds fresh with fewer images
    for f in os.listdir(EMPLOYEES_DIR):
        if f.endswith('.pkl'):
            os.remove(os.path.join(EMPLOYEES_DIR, f))
            print(f"\n  [TRASH]  Deleted old cache: {f}")
    
    print(f"\n{'='*60}")
    print(f"  DONE! Kept {total_kept} images, deleted {total_deleted} images.")
    print(f"  Cache cleared — will rebuild on next startup (~20 seconds).")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
