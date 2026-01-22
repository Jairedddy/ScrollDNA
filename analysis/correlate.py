from analysis.classify import classify_effect

def build_frame_scroll_map(scroll_log, total_frames):
    if not scroll_log:
        return {}
    
    max_scroll = scroll_log[-1]['scrollY']
    frame_scroll = {}
    
    for i in range(total_frames):
        ratio = i / max(1, total_frames - 1)
        frame_scroll[i] = ratio * max_scroll
        
    return frame_scroll

def attach_scroll_to_tracks(tracks, frame_scroll_map):
    enriched = []

    for t in tracks:
        scroll_positions = [
            frame_scroll_map.get(f) for f in t["frames"]
            if f in frame_scroll_map
        ]

        if not scroll_positions:
            continue

        enriched.append({
            **t,
            "scroll_start": min(scroll_positions),
            "scroll_end": max(scroll_positions)
        })

    return enriched

def compute_motion_ratio(track):
    scroll_delta = max(1, track["scroll_end"] - track["scroll_start"])
    motion_delta = abs(track["avg_dy"]) + abs(track["avg_dx"])
    return motion_delta / scroll_delta


def build_effects(tracks):
    effects = []

    for t in tracks:
        t["motion_ratio"] = compute_motion_ratio(t)
        effect, confidence = classify_effect(t)

        if effect == "unknown":
            continue

        effects.append({
            "type": effect,
            "scroll_range": [
                round(t["scroll_start"], 1),
                round(t["scroll_end"], 1)
            ],
            "motion_ratio": round(t["motion_ratio"], 3),
            "confidence": confidence
        })

    return effects
