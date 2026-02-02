"""Tests for Ken Burns effect in video_effects.py."""

import sys
from pathlib import Path

# Ensure project root is on path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pytest

from video_effects import create_logo_intro_clip


def test_ken_burns_clip_duration(small_logo_path):
    pan_duration = 2
    hold_duration = 3
    clip = create_logo_intro_clip(
        small_logo_path,
        width=100,
        height=100,
        pan_duration=pan_duration,
        hold_duration=hold_duration,
    )
    try:
        assert clip.duration == pan_duration + hold_duration
    finally:
        clip.close()


def test_ken_burns_clip_fps(small_logo_path):
    clip = create_logo_intro_clip(small_logo_path, width=50, height=50, fps=24)
    try:
        assert clip.fps == 24
    finally:
        clip.close()


def test_ken_burns_raises_on_missing_logo():
    import os
    # Use a path that does not exist on any platform
    bad_path = os.path.join(os.path.sep, "nonexistent", "path", "logo.png")
    with pytest.raises(FileNotFoundError, match="Logo not found"):
        create_logo_intro_clip(bad_path)


def test_ken_burns_custom_dimensions(small_logo_path):
    width, height = 320, 240
    clip = create_logo_intro_clip(
        small_logo_path,
        width=width,
        height=height,
        pan_duration=0.5,
        hold_duration=0.5,
    )
    try:
        frame = clip.get_frame(0)
        assert frame.shape == (height, width, 3)
    finally:
        clip.close()


def test_ken_burns_frame_at_t0(small_logo_path):
    width, height = 64, 48
    clip = create_logo_intro_clip(
        small_logo_path,
        width=width,
        height=height,
        pan_duration=0.5,
        hold_duration=0.5,
    )
    try:
        frame = clip.get_frame(0)
        assert frame.shape == (height, width, 3)
        assert frame.dtype.name == "uint8"
    finally:
        clip.close()


def test_ken_burns_frame_at_hold(small_logo_path):
    pan_duration = 0.5
    hold_duration = 0.5
    width, height = 64, 48
    clip = create_logo_intro_clip(
        small_logo_path,
        width=width,
        height=height,
        pan_duration=pan_duration,
        hold_duration=hold_duration,
    )
    try:
        # Frame during hold phase (after pan)
        t_hold = pan_duration + 0.1
        frame = clip.get_frame(t_hold)
        assert frame.shape == (height, width, 3)
    finally:
        clip.close()
