"""Video effects (e.g., Ken Burns logo intro)."""

from pathlib import Path

from PIL import Image
import numpy as np

try:
    from moviepy import VideoClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


def create_logo_intro_clip(logo_path, width=1920, height=1080, pan_duration=8, hold_duration=15, fps=30):
    """Create a video clip with Ken Burns effect on the logo: pan left-to-right, then hold full width.

    Phase 1 (0 to pan_duration): Pan across image from left to right, ending with full width in frame.
    Phase 2 (pan_duration to pan_duration+hold_duration): Static full-width logo.

    Args:
        logo_path: Path to images/logo.png
        width, height: Video dimensions (black background)
        pan_duration: Seconds for the Ken Burns pan
        hold_duration: Seconds to hold full logo after pan
        fps: Frame rate

    Returns:
        VideoClip (no audio)
    """
    if not MOVIEPY_AVAILABLE:
        raise RuntimeError("moviepy is required for Ken Burns effect")

    logo_path = Path(logo_path)
    if not logo_path.exists():
        raise FileNotFoundError(f"Logo not found: {logo_path}")

    img = Image.open(logo_path).convert("RGBA")
    img_w, img_h = img.size

    # Letterbox: fit logo to frame maintaining aspect ratio, on black
    frame_aspect = width / height
    img_aspect = img_w / img_h

    if img_aspect > frame_aspect:
        fit_w, fit_h = width, int(width / img_aspect)
    else:
        fit_w, fit_h = int(height * img_aspect), height

    # Composite onto black background (handle transparency)
    logo_rgb = Image.new("RGB", img.size, (0, 0, 0))
    logo_rgb.paste(img, mask=img.split()[3])
    logo_resized = logo_rgb.resize((fit_w, fit_h), Image.Resampling.LANCZOS)
    x_centered = (width - fit_w) // 2
    y_centered = (height - fit_h) // 2

    total_duration = pan_duration + hold_duration
    logo_arr = np.array(logo_resized)

    def make_frame(t):
        if t < 0:
            t = 0
        elif t >= total_duration:
            t = total_duration - 0.001

        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = 0

        if t < pan_duration:
            # Ken Burns: sweep left to right, zoom out to full width.
            # Start: zoomed in on left portion; End: full logo centered
            progress = t / pan_duration
            ease = progress * progress * (3 - 2 * progress)
            scale = 1.3 - 0.3 * ease
            crop_w = max(1, int(fit_w / scale))
            crop_h = max(1, int(fit_h / scale))
            # Pan right: start src_x=0 (left), end with crop centered
            src_x = int((fit_w - crop_w) * ease * 0.5)
            src_y = (fit_h - crop_h) // 2
            src_x = max(0, min(src_x, fit_w - crop_w))
            src_y = max(0, min(src_y, fit_h - crop_h))
            crop = logo_arr[src_y : src_y + crop_h, src_x : src_x + crop_w]
            if crop.size == 0:
                return frame
            # Preserve aspect ratio: scale crop to fit within frame, letterbox on black
            crop_aspect = crop_w / crop_h if crop_h else 1
            frame_aspect = width / height
            if crop_aspect > frame_aspect:
                display_w, display_h = width, max(1, int(width / crop_aspect))
            else:
                display_w, display_h = max(1, int(height * crop_aspect)), height
            scaled = Image.fromarray(crop).resize((display_w, display_h), Image.Resampling.LANCZOS)
            px = (width - display_w) // 2
            py = (height - display_h) // 2
            frame[py:py + display_h, px:px + display_w] = np.array(scaled)[:display_h, :display_w]
        else:
            # Hold: static full logo centered on black
            y1 = y_centered
            x1 = x_centered
            frame[y1:y1 + fit_h, x1:x1 + fit_w] = logo_arr

        return frame

    clip = VideoClip(make_frame, duration=total_duration)
    clip = clip.with_fps(fps)
    return clip
