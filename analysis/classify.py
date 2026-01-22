def classify_effect(track):
    dx = track["avg_dx"]
    dy = track["avg_dy"]
    ratio = track["motion_ratio"]

    # Sticky: no motion but persists across scroll
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return "sticky", "high"

    # Parallax: vertical motion slower than scroll
    if abs(dy) > abs(dx) and ratio < 0.6:
        return "parallax", "medium"

    # Horizontal translate on vertical scroll
    if abs(dx) > abs(dy):
        return "horizontal_translate", "medium"

    # Fallback
    return "unknown", "low"
