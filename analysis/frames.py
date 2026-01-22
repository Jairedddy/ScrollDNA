import cv2
import os

def extract_frames(video_path, output_dir, every_n_frames=3):
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    
    frame_idx = 0
    saved = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % every_n_frames == 0:
            path = f"{output_dir}/frame_{frame_idx:04d}.png"
            cv2.imwrite(path, frame)
            saved += 1
            
        frame_idx += 1
    
    cap.release()
    return saved