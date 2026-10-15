"""
VisionCut Storyboard Generator.
Extracts 12 structured narrative frames across a video with timecode timestamps,
arranged in a 4x3 grid for AI Vision inspection via view_file.
"""

import sys
import os
import cv2
import numpy as np

def generate_storyboard(video_path: str, output_image_path: str, num_frames: int = 12):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open {video_path}")
        return False

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    # Sample points: slightly offset from exact 0 and exact end
    indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)

    frames = []
    times = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            frame = np.zeros((270, 480, 3), dtype=np.uint8)
        else:
            frame = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_AREA)

        t_sec = idx / fps
        times.append(t_sec)

        # Draw timecode banner on frame
        tc_text = f"#{len(frames)+1}  [{t_sec:05.2f}s]"
        cv2.rectangle(frame, (0, 0), (220, 36), (0, 0, 0), -1)
        cv2.putText(frame, tc_text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        frames.append(frame)

    cap.release()

    # Layout into 3 rows of 4 columns
    cols = 4
    rows = 3
    row_images = []
    for r in range(rows):
        row_frames = frames[r * cols : (r + 1) * cols]
        row_images.append(np.hstack(row_frames))

    grid = np.vstack(row_images)

    # Add header banner with file info and total duration
    banner = np.zeros((50, grid.shape[1], 3), dtype=np.uint8)
    header_text = f"FILE: {os.path.basename(video_path)}  |  TOTAL DURATION: {duration:.2f}s  |  FRAMES: {num_frames}"
    cv2.putText(banner, header_text, (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

    final_image = np.vstack([banner, grid])

    os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)
    cv2.imwrite(output_image_path, final_image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"Storyboard saved: {output_image_path} (Duration: {duration:.2f}s)")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_storyboard.py <video_path> <output_image_path>")
        sys.exit(1)
    generate_storyboard(sys.argv[1], sys.argv[2])
