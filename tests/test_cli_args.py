"""Tests for display.py CLI argument parsing."""

import sys
from pathlib import Path

# Ensure project root is on path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from display import create_parser


def test_text_argument():
    parser = create_parser()
    args = parser.parse_args(["HELLO"])
    assert args.text == "HELLO"


def test_input_file_argument():
    parser = create_parser()
    args = parser.parse_args(["-i", "input.txt"])
    assert args.input_file == "input.txt"


def test_video_flag():
    parser = create_parser()
    args = parser.parse_args(["X", "-v"])
    assert args.video is True


def test_file_output():
    parser = create_parser()
    args = parser.parse_args(["X", "-v", "-f", "out.mp4"])
    assert args.file == "out.mp4"


def test_effective_speed():
    parser = create_parser()
    args = parser.parse_args(["X", "--effective-speed", "20"])
    assert args.effective_speed == 20


def test_character_speed():
    parser = create_parser()
    args = parser.parse_args(["X", "--character-speed", "25"])
    assert args.character_speed == 25


def test_title_argument():
    parser = create_parser()
    args = parser.parse_args(["X", "-v", "--title", "My Title"])
    assert args.title == "My Title"


def test_subtitle_argument():
    parser = create_parser()
    args = parser.parse_args(["X", "-v", "--subtitle", "Sub"])
    assert args.subtitle == "Sub"


def test_detailtitle_argument():
    parser = create_parser()
    args = parser.parse_args(["X", "-v", "--detailtitle", "Details"])
    assert args.detailtitle == "Details"


def test_intro_length_duration():
    parser = create_parser()
    args = parser.parse_args(["X", "-v", "--intro-length-duration", "10"])
    assert args.intro_length_duration == 10


def test_defaults():
    parser = create_parser()
    args = parser.parse_args(["X"])
    assert args.effective_speed == 18
    assert args.character_speed == 20
    assert args.intro_length_duration == 15
