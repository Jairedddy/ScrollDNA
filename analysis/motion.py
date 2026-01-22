import cv2
import numpy as np


def diff_frames(frame_a, frame_b, threshold=25):
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
    
    diff = cv2.absdiff(gray_a, gray_b)
    _, thresh = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
    
    return thresh

def extract_motion_regions(diff_mask, min_area=500):
    contours, _ = cv2.findContours(
        diff_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    
    regions = []
    for c in contours:
        area = cv2.contourArea(c)
        if area > min_area:
            x, y, w, h = cv2.boundingRect(c)
            regions.append((x, y, w, h))
            
    return regions

def track_regions(region_sequences, max_dist=40):
    tracks = []
    track_id = 0
    
    for frame_idx, regions in enumerate(region_sequences):
        for r in regions:
            x, y, w, h = r
            cx, cy = x + w/2, y + h/2
            
            matched = False
            for t in tracks:
                px, py = t["last_center"]
                if abs(cx-px) < max_dist and abs(cy-py) < max_dist:
                    t["frames"].append(frame_idx),
                    t["centers"].append((cx, cy))
                    t["last_center"] = (cx, cy)
                    matched = True
                    break
            
            if not matched:
                tracks.append({
                    "id": track_id,
                    "frames": [frame_idx],
                    "centers": [(cx, cy)],
                    "last_center": (cx, cy)
                })
                track_id += 1
                
    return tracks

def summarize_tracks(tracks):
    summaries = []

    for t in tracks:
        if len(t["centers"]) < 3:
            continue

        dx = []
        dy = []

        for i in range(1, len(t["centers"])):
            x1, y1 = t["centers"][i - 1]
            x2, y2 = t["centers"][i]
            dx.append(x2 - x1)
            dy.append(y2 - y1)

        summaries.append({
            "track_id": t["id"],
            "avg_dx": sum(dx) / len(dx),
            "avg_dy": sum(dy) / len(dy),
            "frames": t["frames"]
        })

    return summaries
