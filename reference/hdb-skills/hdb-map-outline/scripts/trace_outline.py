"""
Extract a coastline/shape outline from a user-uploaded reference image (a solid-color
shape on a plain or transparent/checkered background), simplify it to a clean polygon,
verify it visually, and rescale it into an SVG viewBox's map region.

Requires: opencv-python-headless (pip install opencv-python-headless --break-system-packages)

Usage:
    Edit IMAGE_PATH and the mask logic (if the shape isn't green) below, then run.
    Outputs:
      - outline_check.png   -- the traced polygon overlaid on the original, for visual QA
      - outline_scaled.json -- the final points, ready to paste into your dashboard's SVG
"""
import cv2
import numpy as np
import json

IMAGE_PATH = "/mnt/user-data/uploads/YOUR_IMAGE.png"

# The SVG map region these points should be rescaled into -- match your dashboard's
# svg viewBox and the same region used by your lat/lon town projection.
MAP_LEFT, MAP_RIGHT, MAP_TOP, MAP_BOTTOM = 28, 612, 28, 412

# Simplification aggressiveness: fraction of the contour's perimeter used as the
# approxPolyDP epsilon. 0.003-0.005 is a good starting range; raise it for fewer,
# blunter points, lower it to hug fine detail more closely.
SIMPLIFY_FACTOR = 0.004


def build_mask(img):
    """
    Default: mask a green shape on a light/checkered background.
    If your shape has real alpha transparency, prefer that instead:
        alpha = img[:,:,3]; mask = (alpha > 128).astype(np.uint8)*255
    If it's a different solid color, adjust the channel comparison accordingly.
    """
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    mask = ((g > r + 15) & (g > b + 15)).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def main():
    img = cv2.imread(IMAGE_PATH, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"Could not read {IMAGE_PATH}")

    mask = build_mask(img)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise SystemExit("No contour found -- check the mask logic matches your image's colors.")

    biggest = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(biggest, True)
    approx = cv2.approxPolyDP(biggest, SIMPLIFY_FACTOR * peri, True)
    pts = approx.reshape(-1, 2).tolist()
    print(f"Simplified to {len(pts)} points.")

    # Visual QA overlay -- always look at this before trusting the trace
    overlay = img[:, :, :3].copy() if img.shape[2] == 4 else img.copy()
    pts_np = np.array(pts, np.int32).reshape(-1, 1, 2)
    cv2.polylines(overlay, [pts_np], True, (0, 0, 255), 3)
    for p in pts:
        cv2.circle(overlay, tuple(p), 4, (255, 0, 0), -1)
    cv2.imwrite("outline_check.png", overlay)
    print("Wrote outline_check.png -- view it before proceeding.")

    # Rescale onto the SVG map region
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

    def scale(pt):
        x, y = pt
        nx = MAP_LEFT + (x - minx) / (maxx - minx) * (MAP_RIGHT - MAP_LEFT)
        ny = MAP_TOP + (y - miny) / (maxy - miny) * (MAP_BOTTOM - MAP_TOP)
        return round(nx, 1), round(ny, 1)

    scaled = [scale(p) for p in pts]
    with open("outline_scaled.json", "w") as f:
        json.dump(scaled, f)
    print("Wrote outline_scaled.json:")
    print(scaled)


if __name__ == "__main__":
    main()
