"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def small_logo_path():
    """Return path to a small test logo (10x10 red PNG). Creates fixture if missing."""
    project_root = Path(__file__).parent.parent
    fixture_dir = Path(__file__).parent / "fixtures"
    fixture_dir.mkdir(exist_ok=True)
    logo_path = fixture_dir / "small_logo.png"
    if not logo_path.exists():
        try:
            from PIL import Image
            img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
            img.save(logo_path)
        except ImportError:
            # Fallback to project logo if Pillow unavailable
            fallback = project_root / "images" / "logo.png"
            if fallback.exists():
                return fallback
            pytest.skip("Pillow required to create fixture or images/logo.png")
    return logo_path
