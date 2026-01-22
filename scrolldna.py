import sys, json, os, shutil, time, re, cv2
from urllib.parse import urlparse
from capture.browser import launch_browser
from capture.scroll import scroll_page
from capture.dom import snapshot_dom
from analysis.frames import extract_frames
from analysis.motion import diff_frames, extract_motion_regions, track_regions, summarize_tracks

if len(sys.argv) < 2:
    print("Error: URL argument is required")
    print("Usage: python scrolldna.py <url> [speed]")
    print("  Example: python scrolldna.py https://example.com 2x")
    print("  Speed format: 2x, 1.5x, 0.5x, 3x, etc. (default: 1x)")
    sys.exit(1)

url = sys.argv[1]

if not url.startswith(('http://', 'https://')):
    url = 'https://' + url

speed_multiplier = 1.0  
if len(sys.argv) >= 3:
    speed_arg = sys.argv[2].lower().strip()
    match = re.match(r'^(\d+\.?\d*)x?$', speed_arg)
    if match:
        speed_multiplier = float(match.group(1))
        print(f"Scroll speed set to {speed_multiplier}x")
    else:
        print(f"Warning: Invalid speed format '{speed_arg}'. Using default speed (1x).")
        print("Speed format should be like: 2x, 1.5x, 0.5x, etc.")

pw, browser, context, page = launch_browser()
page.goto(url, wait_until="networkidle")

time.sleep(1.0)

try:
    cdp_session = context.new_cdp_session(page)
    targets_response = cdp_session.send("Target.getTargets")
    target_infos = targets_response.get("targetInfos", [])
    
    page_target = None
    for target in target_infos:
        if target.get("type") == "page":
            page_target = target
            break
    
    if page_target:
        window_info = cdp_session.send("Browser.getWindowForTarget", {"targetId": page_target["targetId"]})
        window_id = window_info.get("windowId")
        
        if window_id:
            cdp_session.send("Browser.setWindowBounds", {
                "windowId": window_id,
                "bounds": {"windowState": "maximized"}
            })
            time.sleep(1.0)
except Exception as e:
    print(f"Note: Could not maximize window automatically: {e}")
    print("Please maximize the browser window manually.")

scroll_step = int(120 * speed_multiplier)
scroll_log = scroll_page(page, step=scroll_step)

dom_snapshots = snapshot_dom(page)

parsed_url = urlparse(url)
website_name = parsed_url.netloc or parsed_url.path.split('/')[0]
website_name = website_name.split(':')[0]
website_name = website_name.replace('.', '_')

run_dir = f"output/runs/{website_name}"
os.makedirs(run_dir, exist_ok=True)

with open(f"{run_dir}/scroll_log.json", "w") as f:
    json.dump(scroll_log, f, indent=2)

with open(f"{run_dir}/dom_snapshots.json", "w") as f:
    json.dump(dom_snapshots, f, indent=2)

video_path = page.video.path() if page.video else None

context.close()

if video_path and os.path.exists(video_path):
    video_ext = os.path.splitext(video_path)[1] or '.webm'
    new_video_path = os.path.join(run_dir, f"{website_name}{video_ext}")
    shutil.move(video_path, new_video_path)
    print(f"Video saved to: {new_video_path}")
else:
    print("Warning: Video file not found or could not be accessed")

browser.close()
pw.stop()

def find_recorded_video(run_dir):
    for root, _, files in os.walk(run_dir):
        for f in files:
            if f.endswith(".webm") or f.endswith(".mp4"):
                return os.path.join(root, f)
    return None

video_path = find_recorded_video(run_dir)

frames_dir = f"{run_dir}/frames"
frame_count = extract_frames(
    video_path=video_path,
    output_dir=frames_dir,
    every_n_frames=3
)

frame_files = sorted(os.listdir(frames_dir))
region_sequences = []

for i in range(len(frame_files) - 1):
    f1 = cv2.imread(os.path.join(frames_dir, frame_files[i]))
    f2 = cv2.imread(os.path.join(frames_dir, frame_files[i + 1]))

    diff = diff_frames(f1, f2)
    regions = extract_motion_regions(diff)

    region_sequences.append(regions)

tracks = track_regions(region_sequences)
motion_tracks = summarize_tracks(tracks)

with open(f"{run_dir}/motion_tracks.json", "w") as f:
    json.dump(motion_tracks, f, indent=2)
