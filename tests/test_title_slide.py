"""Tests for title slide generation in video_creation.py.

Verifies that create_title_slide_image runs non-interactively (no user prompts).
Requires LibreOffice and the slides/video-title.odp template.
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pytest

from video_creation import create_title_slide_image


@pytest.mark.timeout(120)
def test_title_slide_generation_non_interactive():
    """Title slide PNG is generated without requiring user interaction.

    Calls LibreOffice headless with CREATE_NO_WINDOW (Windows) and isolated
    profile. If this hangs, it suggests console popups or prompts are blocking.
    """
    odp_path = _project_root / "slides" / "video-title.odp"
    if not odp_path.exists():
        pytest.skip("ODP template not found: slides/video-title.odp")

    try:
        png_path = create_title_slide_image(
            title="Test Title",
            subtitle="Test Subtitle",
            detailtitle="Test Details",
            odp_path=odp_path,
            output_width=320,
            output_height=180,
        )
    except RuntimeError as e:
        if "LibreOffice" in str(e):
            pytest.skip("LibreOffice not available or not on PATH")
        raise

    try:
        png = Path(png_path)
        assert png.exists()
        assert png.stat().st_size > 0
        with open(png_path, "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n"
    finally:
        Path(png_path).unlink(missing_ok=True)
