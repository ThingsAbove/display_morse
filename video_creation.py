"""Video generation: morse content assembly, title slide (ODP), intro clips, and output."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np

from display import (
    MOVIEPY_AVAILABLE,
    calculate_token_duration,
    create_video_frame_with_markup,
    generate_audio_from_events,
    parse_markup,
)

try:
    from moviepy import AudioFileClip, ImageClip, VideoClip, concatenate_videoclips, vfx
except ImportError:
    vfx = None

from video_effects import create_logo_intro_clip


def _escape_xml_text(s):
    """Escape XML special characters for safe inclusion in ODF content."""
    if s is None or s == "":
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def create_title_slide_image(title, subtitle, detailtitle, odp_path, output_width=1920, output_height=1080):
    """Create a PNG image from the ODP template with TITLE/SUBTITLE/DETAILS replaced.

    Uses LibreOffice headless to render. Font size and color from the template are preserved.

    Args:
        title: Text to replace TITLE placeholder
        subtitle: Text to replace SUBTITLE placeholder
        detailtitle: Text to replace DETAILS placeholder
        odp_path: Path to slides/video-title.odp
        output_width, output_height: Desired image dimensions (default 1920x1080)

    Returns:
        Path to the generated PNG.
    """
    odp_path = Path(odp_path)
    if not odp_path.exists():
        raise FileNotFoundError(f"ODP template not found: {odp_path}")

    # Resolve soffice (LibreOffice) - try PATH names, then common install paths.
    # On Windows, soffice.com is the CLI wrapper; use CREATE_NO_WINDOW to avoid
    # console popups that block the subprocess.
    soffice_candidates = ["soffice", "libreoffice", "soffice.exe"]
    if sys.platform == "win32":
        soffice_candidates = ["soffice.com", "soffice", "libreoffice", "soffice.exe"]
        prog = os.environ.get("ProgramFiles", "C:\\Program Files")
        prog86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        soffice_candidates.extend([
            str(Path(prog) / "LibreOffice" / "program" / "soffice.com"),
            str(Path(prog) / "LibreOffice" / "program" / "soffice.exe"),
            str(Path(prog86) / "LibreOffice" / "program" / "soffice.com"),
            str(Path(prog86) / "LibreOffice" / "program" / "soffice.exe"),
        ])
    _no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    soffice = None
    for name in soffice_candidates:
        try:
            r = subprocess.run(
                [name, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_no_window,
            )
            if r.returncode == 0:
                soffice = name
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if soffice is None:
        raise RuntimeError(
            "LibreOffice is required for title slide generation. "
            "Install LibreOffice and ensure 'soffice' is on your PATH, or install to "
            "C:\\Program Files\\LibreOffice."
        )

    title = _escape_xml_text(title) if title else ""
    subtitle = _escape_xml_text(subtitle) if subtitle else ""
    detailtitle = _escape_xml_text(detailtitle) if detailtitle else ""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        # Extract ODP (it's a ZIP)
        with zipfile.ZipFile(odp_path, "r") as z:
            z.extractall(tmppath)

        content_xml = tmppath / "content.xml"
        content = content_xml.read_text(encoding="utf-8")
        # Replace SUBTITLE and DETAILS before TITLE, since "TITLE" is a substring of "SUBTITLE"
        content = content.replace("SUBTITLE", subtitle).replace("DETAILS", detailtitle).replace("TITLE", title)
        content_xml.write_text(content, encoding="utf-8")

        # Rezip to temp ODP
        temp_odp = tmppath / "title_slide.odp"
        with zipfile.ZipFile(temp_odp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in tmppath.rglob("*"):
                if f.is_file() and f != temp_odp:
                    arcname = f.relative_to(tmppath)
                    z.write(f, arcname)

        # LibreOffice convert to PNG
        outdir = tmppath / "out"
        outdir.mkdir(exist_ok=True)
        # Use isolated profile to avoid first-run wizard and user prompts
        profile_dir = tmppath / "lo_profile"
        profile_dir.mkdir(exist_ok=True)
        profile_uri = Path(profile_dir.resolve()).as_uri()
        filter_spec = f'png:impress_png_Export:{{"PixelWidth":{output_width},"PixelHeight":{output_height}}}'
        base_cmd = [
            soffice,
            "--headless",
            "--nofirststartwizard",
            "--norestore",
            "-env:UserInstallation=" + profile_uri,
            "--convert-to",
            filter_spec,
            "--outdir",
            str(outdir),
            str(temp_odp),
        ]
        fallback_cmd = [
            soffice,
            "--headless",
            "--nofirststartwizard",
            "--norestore",
            "-env:UserInstallation=" + profile_uri,
            "--convert-to",
            "png",
            "--outdir",
            str(outdir),
            str(temp_odp),
        ]
        result = None
        last_error = None
        for attempt in range(3):
            result = subprocess.run(
                base_cmd, capture_output=True, text=True, timeout=60, cwd=str(tmppath),
                creationflags=_no_window,
            )
            if result.returncode == 0:
                break
            last_error = result.stderr or result.stdout
            if attempt < 2:
                time.sleep(2)
        if result is None or result.returncode != 0:
            # Retry with simple conversion
            for attempt in range(3):
                result = subprocess.run(
                    fallback_cmd, capture_output=True, text=True, timeout=60, cwd=str(tmppath),
                    creationflags=_no_window,
                )
                if result.returncode == 0:
                    break
                last_error = result.stderr or result.stdout
                if attempt < 2:
                    time.sleep(2)
        if result is None or result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed after retries: {last_error}"
            )

        # Find output PNG
        png_files = list(outdir.glob("*.png"))
        if not png_files:
            raise RuntimeError("LibreOffice did not produce a PNG output")
        png_path = png_files[0]

        persistent_temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        persistent_temp.close()
        shutil.copy(png_path, persistent_temp.name)
        return persistent_temp.name


def generate_intro_clips(title, subtitle, detailtitle, intro_length_duration, project_root=None):
    """Generate intro clips: title slide (3 sec) + logo Ken Burns + hold.

    Returns list of VideoClips to prepend, or empty list if title is not set.
    """
    if not title or not title.strip():
        return []

    project_root = Path(project_root or os.path.dirname(os.path.abspath(__file__)))
    odp_path = project_root / "slides" / "video-title.odp"
    logo_path = project_root / "images" / "logo.png"

    clips = []

    # Title slide: 3 seconds with 1 second fade in
    png_path = create_title_slide_image(title, subtitle or "", detailtitle or "", odp_path)
    try:
        title_clip = ImageClip(png_path, duration=3)
        title_clip = title_clip.with_fps(30)
        if vfx:
            title_clip = title_clip.with_effects([vfx.FadeIn(1)])
        clips.append(title_clip)
    finally:
        if png_path and os.path.exists(png_path):
            try:
                os.unlink(png_path)
            except OSError:
                pass

    # Logo intro: 8 sec pan + intro_length_duration hold, 1s fade in, 1.5s fade out
    logo_clip = create_logo_intro_clip(
        logo_path,
        pan_duration=8,
        hold_duration=intro_length_duration,
    )
    if vfx:
        logo_clip = logo_clip.with_effects([vfx.FadeIn(1), vfx.FadeOut(1.5)])
    clips.append(logo_clip)

    return clips


def generate_video(text, output_file, effective_speed=18, character_speed=18, title=None, subtitle=None, detailtitle=None, intro_length_duration=15):
    """Generate HD video with synchronized text and audio."""
    if not MOVIEPY_AVAILABLE:
        print("Error: moviepy and Pillow are required for video generation")
        sys.exit(1)

    print("Generating video...")
    print(f"Text: {text}")

    tokens, display_chars, events = parse_markup(text, effective_speed=effective_speed, character_speed=character_speed)
    display_text = "".join([m["ch"] for m in display_chars])
    print(f"Display text: {display_text}")

    print("Calculating token timings...")
    current_time = 0.0
    segments = []

    for ev in events:
        if ev["kind"] == "pause":
            dur = float(ev["seconds"])
            segments.append(
                {"kind": "pause", "start": current_time, "end": current_time + dur}
            )
            current_time += dur
        else:
            token = ev["token"]
            dur = calculate_token_duration(token, effective_speed, character_speed)
            segments.append(
                {
                    "kind": "token",
                    "token_idx": ev["token_idx"],
                    "token": token,
                    "start": current_time,
                    "end": current_time + dur,
                }
            )
            current_time += dur

    total_duration = current_time
    print(f"Total duration: {total_duration:.2f} seconds")

    print("Generating audio track...")
    temp_audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_audio_file.close()

    audio_generator = generate_audio_from_events(events, effective_speed=effective_speed, character_speed=character_speed)
    with open(temp_audio_file.name, "wb") as f:
        import audiogen_p3
        audiogen_p3.write_wav(f, audio_generator)

    width, height = 1920, 1080
    fps = 30
    font_size = 100

    def make_frame(t):
        if t < 0:
            t = 0
        elif t >= total_duration:
            t = total_duration

        reveal_token_idx = 0
        active_token_idx = None

        if t >= total_duration:
            reveal_token_idx = len(tokens)
            active_token_idx = None
        else:
            for seg in segments:
                if t < seg["end"]:
                    if seg["kind"] == "token":
                        active_token_idx = seg["token_idx"]
                        reveal_token_idx = seg["token_idx"]
                    else:
                        active_token_idx = None
                    break
                if seg["kind"] == "token":
                    reveal_token_idx = seg["token_idx"] + 1

        frame_img = create_video_frame_with_markup(
            display_text,
            display_chars,
            reveal_token_idx,
            active_token_idx,
            len(tokens),
            width,
            height,
            font_size,
        )
        return np.array(frame_img)

    print("Creating video frames...")
    video = VideoClip(make_frame, duration=total_duration)
    video = video.with_fps(fps)

    print("Adding audio track...")
    audio = AudioFileClip(temp_audio_file.name)
    video = video.with_audio(audio)

    intro_clips = []
    endroll_clip = None
    if title and title.strip():
        print("Generating title slide and logo intro...")
        project_root = os.path.dirname(os.path.abspath(__file__))
        intro_clips = generate_intro_clips(
            title, subtitle, detailtitle, intro_length_duration, project_root
        )
        # End roll: 8 sec pan + 10 sec hold, 1s fade in, 3s fade out
        logo_path = Path(project_root) / "images" / "logo.png"
        endroll_clip = create_logo_intro_clip(
            logo_path,
            pan_duration=8,
            hold_duration=10,
        )
        if vfx:
            endroll_clip = endroll_clip.with_effects([vfx.FadeIn(1), vfx.FadeOut(3)])

    morse_video = video
    all_clips = list(intro_clips) + [morse_video]
    if endroll_clip is not None:
        all_clips.append(endroll_clip)
    if len(all_clips) > 1:
        video = concatenate_videoclips(all_clips, method="compose", bg_color=(0, 0, 0))

    print(f"Writing video to {output_file}...")
    video.write_videofile(output_file, fps=fps, codec='libx264', audio_codec='aac')

    video.close()
    if len(all_clips) > 1:
        morse_video.close()
    for c in intro_clips:
        c.close()
    if endroll_clip is not None:
        endroll_clip.close()
    audio.close()
    os.unlink(temp_audio_file.name)

    print(f"Video generation complete: {output_file}")
