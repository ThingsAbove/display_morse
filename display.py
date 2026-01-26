import os, time, sys
import argparse
import tempfile
import math
import re
from koch_trainer import KochTrainerAudioGen

try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: moviepy and/or Pillow not installed. Video generation requires:")
    print("  pip install moviepy Pillow imageio-ffmpeg")


def _get_morse_tables(effective_speed=18, character_speed=20):
    """Return (valid_prosigns, supported_tokens) from KochTrainerAudioGen."""
    temp_gen = KochTrainerAudioGen("", effective_speed=effective_speed, character_speed=character_speed)
    supported_tokens = set(temp_gen._letters.keys())
    valid_prosigns = {k for k in supported_tokens if len(k) > 1}
    return valid_prosigns, supported_tokens


def parse_markup(text, effective_speed=18, character_speed=20):
    """Parse text into timed Morse tokens + display characters.

    Supports:
    - Prosigns in angle brackets, e.g. "<AR>" (timed, converted to token "AR", displayed as "AR")
    - Informational segments in square brackets, e.g. "[Note: ...]" (NOT timed; displayed as-is WITHOUT the brackets; case preserved)
    - Commands in braces, e.g. "{p05}" (NOT displayed; affects timing depending on command)
    - Newlines / carriage returns (timed as a space, displayed as a newline)

    Returns:
        tuple: (morse_tokens, display_chars, events) where:
            - morse_tokens: list[str] timed tokens to feed to KochTrainerAudioGen / timing
            - display_chars: list[dict] one per displayed character, with metadata:
                - ch: the character to display (may be '\\n')
                - token_idx: int | None, the timed token index (None for info chars)
                - is_prosign: bool
                - is_info: bool
                - info_anchor: int | None, token index at which the whole info segment appears
            - events: list[dict] ordered playback events. Each is either:
                - {"kind": "token", "token_idx": int, "token": str}
                - {"kind": "pause", "seconds": float}
    """
    valid_prosigns, supported_tokens = _get_morse_tables(
        effective_speed=effective_speed, character_speed=character_speed
    )

    morse_tokens = []
    display_chars = []
    events = []
    token_idx = 0

    def add_info_segment(segment, anchor):
        for ch in segment:
            if ch == "\r":
                ch = "\n"
            display_chars.append(
                {
                    "ch": ch,
                    "token_idx": None,
                    "is_prosign": False,
                    "is_info": True,
                    "info_anchor": anchor,
                }
            )

    i = 0
    while i < len(text):
        ch = text[i]

        # Commands: not displayed. Currently supported: {p##} pause in seconds.
        if ch == "{":
            end_idx = text.find("}", i + 1)
            if end_idx != -1:
                cmd = text[i + 1 : end_idx].strip()
                m = re.match(r"^[pP](\d+(?:\.\d+)?)$", cmd)
                if m:
                    seconds = float(m.group(1))
                    if seconds > 0:
                        events.append({"kind": "pause", "seconds": seconds})
                # Always consume brace commands without displaying them.
                i = end_idx + 1
                continue

        # Informational segment: displayed immediately (no timing, no morse), case preserved.
        if ch == "[":
            end_idx = text.find("]", i + 1)
            if end_idx != -1:
                # Do not include the surrounding brackets in the output.
                segment = text[i + 1 : end_idx]
                add_info_segment(segment, anchor=token_idx)
                i = end_idx + 1
                continue

        # Prosign: <AR>, <SK>, etc. (timed).
        if ch == "<":
            end_idx = text.find(">", i + 1)
            if end_idx != -1:
                prosign = text[i + 1 : end_idx].upper()
                if prosign in valid_prosigns:
                    morse_tokens.append(prosign)
                    events.append({"kind": "token", "token_idx": token_idx, "token": prosign})
                    for pch in prosign:
                        display_chars.append(
                            {
                                "ch": pch,
                                "token_idx": token_idx,
                                "is_prosign": True,
                                "is_info": False,
                                "info_anchor": None,
                            }
                        )
                    token_idx += 1
                    i = end_idx + 1
                    continue

        # Newlines / carriage returns: timed as a space, displayed as a newline.
        if ch == "\r":
            ch = "\n"
        if ch == "\n":
            morse_tokens.append(" ")
            events.append({"kind": "token", "token_idx": token_idx, "token": " "})
            display_chars.append(
                {
                    "ch": "\n",
                    "token_idx": token_idx,
                    "is_prosign": False,
                    "is_info": False,
                    "info_anchor": None,
                }
            )
            token_idx += 1
            i += 1
            continue

        # Normalize tabs to spaces.
        if ch == "\t":
            ch = " "

        # Spaces: timed as spaces, displayed as spaces.
        if ch == " ":
            morse_tokens.append(" ")
            events.append({"kind": "token", "token_idx": token_idx, "token": " "})
            display_chars.append(
                {
                    "ch": " ",
                    "token_idx": token_idx,
                    "is_prosign": False,
                    "is_info": False,
                    "info_anchor": None,
                }
            )
            token_idx += 1
            i += 1
            continue

        # Regular character: timed (uppercased for morse), displayed as uppercased.
        token = ch.upper()
        if token not in supported_tokens:
            # Unknown/unsupported: keep the original char in the viewport, but time it as a space.
            morse_tokens.append(" ")
            events.append({"kind": "token", "token_idx": token_idx, "token": " "})
            display_chars.append(
                {
                    "ch": ch,
                    "token_idx": token_idx,
                    "is_prosign": False,
                    "is_info": False,
                    "info_anchor": None,
                }
            )
            token_idx += 1
            i += 1
            continue

        morse_tokens.append(token)
        events.append({"kind": "token", "token_idx": token_idx, "token": token})
        display_chars.append(
            {
                "ch": token,
                "token_idx": token_idx,
                "is_prosign": False,
                "is_info": False,
                "info_anchor": None,
            }
        )
        token_idx += 1
        i += 1

    return morse_tokens, display_chars, events


def parse_prosigns(text):
    """Parse prosigns from angle brackets and return tokenized list.
    
    Args:
        text: Input text that may contain prosigns in angle brackets (e.g., "<BT>")
    
    Returns:
        tuple: (tokens, display_text) where:
            - tokens: List of tokens, each is either a single character, prosign string, or space
            - display_text: Text with prosigns extracted (angle brackets removed)
    """
    # Get valid prosigns from KochTrainerAudioGen
    # Create a temporary instance to access _letters
    temp_gen = KochTrainerAudioGen("", effective_speed=18, character_speed=20)
    valid_prosigns = {k for k in temp_gen._letters.keys() if len(k) > 1}
    
    tokens = []
    display_text = ""
    i = 0
    
    while i < len(text):
        if text[i] == '<':
            # Find the closing bracket
            end_idx = text.find('>', i + 1)
            if end_idx == -1:
                # No closing bracket, treat '<' as regular character
                tokens.append(text[i])
                display_text += text[i]
                i += 1
                continue
            
            # Extract prosign content
            prosign = text[i+1:end_idx].upper()
            
            # Validate prosign exists
            if prosign in valid_prosigns:
                tokens.append(prosign)
                display_text += prosign
                i = end_idx + 1
            else:
                # Invalid prosign, treat as regular characters
                tokens.append(text[i])
                display_text += text[i]
                i += 1
        else:
            # Regular character
            tokens.append(text[i])
            display_text += text[i]
            i += 1
    
    return tokens, display_text

class ColorfulCharacterDisplay:
    def __init__(self, text, effective_speed=18, character_speed=20):
        self.effective_speed = effective_speed
        self.character_speed = character_speed

        # Parse markup (prosigns, info segments, newlines) into timed tokens and display characters
        self.tokens, self.display_chars, self.events = parse_markup(
            text, effective_speed=effective_speed, character_speed=character_speed
        )
        self.token_index = 0  # index into timed tokens
        self.event_index = 0
        self.effective_speed = effective_speed
        self.character_speed = character_speed
        
    def display_character(self):
        if os.name == 'nt':
            # For Windows
            os.system('cls')
        else:
            # For UNIX-based systems (Linux, macOS)
            os.system('clear')

        bright_yellow = "\033[1;33m"
        bright_green = "\033[1;32m"
        bright_red = "\033[1;31m"
        light_blue = "\033[94m"
        reset = "\033[0m"
        
        output_parts = []
        for meta in self.display_chars:
            ch = meta["ch"]

            if ch == "\n":
                # Preserve line breaks, but reveal them progressively like other timed content.
                if meta.get("is_info"):
                    if meta.get("info_anchor") is not None and meta["info_anchor"] <= self.token_index:
                        output_parts.append(reset + "\n")
                else:
                    t_idx = meta.get("token_idx")
                    if t_idx is not None and t_idx <= self.token_index:
                        output_parts.append(reset + "\n")
                continue

            # Info segments appear instantly when reached, do not affect timing.
            if meta["is_info"]:
                if meta["info_anchor"] is not None and meta["info_anchor"] <= self.token_index:
                    output_parts.append(light_blue + ch)
                continue

            # Timed morse chars: show progressively up to current token.
            t_idx = meta["token_idx"]
            if t_idx is None or t_idx > self.token_index:
                continue

            if t_idx < self.token_index:
                output_parts.append((bright_green if meta["is_prosign"] else bright_yellow) + ch)
            else:
                output_parts.append(bright_red + ch)

        print("".join(output_parts) + reset)

    def next(self):
        if self.event_index >= len(self.events):
            return False

        ev = self.events[self.event_index]
        self.event_index += 1

        if ev["kind"] == "pause":
            # Pause should freeze both sound and viewport progression.
            time.sleep(ev["seconds"])
            return True

        token = ev["token"]
        token_idx = ev["token_idx"]

        # Highlight and advance exactly this token index.
        self.token_index = token_idx

        koch_audio = KochTrainerAudioGen(
            token, effective_speed=self.effective_speed, character_speed=self.character_speed
        )
        koch_audio.emit_audio()

        self.display_character()
        self.token_index = token_idx + 1
        return True


def calculate_token_duration(token, effective_speed=18, character_speed=20):
    """Calculate the audio duration for a token (character or prosign) in morse code.
    This must match exactly what KochTrainerAudioGen generates.
    
    IMPORTANT: generate_letter_sound() ALWAYS adds inter_letter*1.6 at the end,
    regardless of what comes next. This includes spaces too!
    
    Args:
        token: The token to calculate duration for (single character or prosign string)
        effective_speed: Effective words per minute (Farnsworth speed)
        character_speed: Character speed in words per minute
    """
    # Create a temporary audio generator to get timing info and access methods
    koch_audio = KochTrainerAudioGen(token, effective_speed=effective_speed, character_speed=character_speed)
    
    # Use the timing values from the audio generator
    dit = koch_audio._dit
    dah = koch_audio._dah
    inter_symbol = koch_audio._inter_symbol
    inter_letter = koch_audio._inter_letter
    inter_word = koch_audio._inter_word
    
    # For spaces, generate_letter_sound(' ') creates:
    # tones = [self.space()]  (one tone generator)
    # spaces = [self.inter_letter]  (one space generator)
    # letter_sound = zip(tones, spaces) = [(space(), inter_letter())]
    # So the actual audio is: space() + inter_letter()
    # Which is: inter_word + inter_letter*1.6
    if token == ' ':
        return inter_word + (inter_letter * 1.6)
    
    # Count dits and dahs in the pattern
    # This works for both regular characters and prosigns
    if token not in koch_audio._letters:
        # Unknown token, use default inter-letter gap
        # generate_letter_sound() always adds inter_letter at the end
        return inter_letter * 1.6
    
    pattern = koch_audio._letters[token]
    num_symbols = len(pattern)
    
    # Calculate duration: symbols + inter-symbol gaps + inter-letter gap
    # This matches generate_letter_sound() which ALWAYS creates:
    # [tone1, inter_symbol, tone2, inter_symbol, ..., toneN, inter_letter*1.6]
    # The inter_letter gap is ALWAYS added, even if the next character is a space
    # Note: Prosigns have no inter-character spacing within them (they're sent as one unit),
    # but they still get the inter_letter gap at the end like regular characters
    duration = 0
    for i, symbol_func in enumerate(pattern):
        if symbol_func == koch_audio.dit:
            duration += dit
        elif symbol_func == koch_audio.dah:
            duration += dah
        elif symbol_func == koch_audio.space:
            duration += inter_word
        
        # Add inter-symbol gap (except after last symbol)
        if i < num_symbols - 1:
            duration += inter_symbol
    
    # Add inter-letter gap (multiplied by 1.6 as in the inter_letter method)
    # This is ALWAYS added by generate_letter_sound(), regardless of what comes next
    duration += inter_letter * 1.6
    
    return duration


# Keep the old function name for backward compatibility
def calculate_character_duration(character, effective_speed=18, character_speed=20):
    """Calculate the audio duration for a single character in morse code.
    Deprecated: Use calculate_token_duration() instead.
    """
    return calculate_token_duration(character, effective_speed, character_speed)


def generate_audio_from_tokens(tokens, effective_speed=18, character_speed=20):
    """Generate audio from a list of tokens (characters and prosigns).
    
    Args:
        tokens: List of tokens (single characters or prosign strings)
        effective_speed: Effective words per minute
        character_speed: Character speed in words per minute
    
    Returns:
        Audio generator that can be saved to file
    """
    import itertools
    import audiogen_p3
    
    # Create audio generator to get filter settings and access generate_letter_sound
    temp_gen = KochTrainerAudioGen("", effective_speed=effective_speed, character_speed=character_speed)
    band_pass_filter = audiogen_p3.filters.band_pass(temp_gen._hertz, temp_gen._bandwidth)
    
    # Generate letter sounds for each token using generate_letter_sound
    letter_sounds = []
    for token in tokens:
        # Use generate_letter_sound to get the sound for this token
        letter_sound = temp_gen.generate_letter_sound(token)
        letter_sounds.append(letter_sound)
    
    # Chain all sounds together and apply filters
    combined_audio = itertools.chain(*letter_sounds)
    filtered_audio = band_pass_filter(band_pass_filter(band_pass_filter(combined_audio)))
    
    return filtered_audio


def generate_audio_from_events(events, effective_speed=18, character_speed=20):
    """Generate audio from token/pause events.

    - token events: emitted via KochTrainerAudioGen.generate_letter_sound()
    - pause events: emitted as exact-length silence
    """
    import itertools
    import audiogen_p3

    temp_gen = KochTrainerAudioGen("", effective_speed=effective_speed, character_speed=character_speed)
    band_pass_filter = audiogen_p3.filters.band_pass(temp_gen._hertz, temp_gen._bandwidth)

    parts = []
    for ev in events:
        if ev["kind"] == "pause":
            parts.append(audiogen_p3.silence(ev["seconds"]))
        else:
            parts.append(temp_gen.generate_letter_sound(ev["token"]))

    combined_audio = itertools.chain(*parts) if parts else itertools.chain()
    filtered_audio = band_pass_filter(band_pass_filter(band_pass_filter(combined_audio)))
    return filtered_audio


def get_wrapped_text_layout(text, font, max_width, padding=40, font_size=100):
    """Calculate character positions with word wrapping.

    Key behavior:
    - Words do NOT wrap mid-word. If the next word won't fit, it starts on the next line.
    - Explicit newlines in the input text ('\\n' or '\\r') force a new line.
    - Returns list of (char, x, y, line_num, text_index) tuples.
    """
    layout = []
    x = padding
    y = 0
    line_num = 0
    line_height = int(font_size * 1.3)

    usable_width = max_width - 2 * padding
    if usable_width < 1:
        usable_width = 1

    space_width = font.getlength(" ")

    i = 0
    pending_space_indices = []

    def newline():
        nonlocal x, y, line_num, pending_space_indices
        pending_space_indices = []
        line_num += 1
        y += line_height
        x = padding

    while i < len(text):
        ch = text[i]

        if ch == "\r":
            ch = "\n"

        if ch == "\n":
            newline()
            i += 1
            continue

        if ch == "\t":
            ch = " "

        # Collect spaces to decide whether they belong on this line.
        if ch == " ":
            pending_space_indices.append(i)
            i += 1
            continue

        # Collect a "word": run of non-space, non-newline characters.
        word_indices = []
        while i < len(text):
            c = text[i]
            if c == "\r":
                c = "\n"
            if c in ("\n", " ", "\t"):
                break
            word_indices.append(i)
            i += 1

        word = "".join(text[idx] for idx in word_indices)
        word_width = font.getlength(word) if word else 0

        # Drop leading spaces at the beginning of a line.
        if x == padding:
            pending_space_indices = []

        current_line_width = x - padding
        spaces_width = space_width * len(pending_space_indices)
        required_width = spaces_width + word_width

        # If it doesn't fit on this line (and we're not already at line start), wrap before the word.
        if current_line_width > 0 and (current_line_width + required_width) > usable_width:
            newline()
            current_line_width = 0
            pending_space_indices = []

        # Lay out pending spaces (for positioning only; caller skips drawing them).
        for s_idx in pending_space_indices:
            layout.append((" ", x, y, line_num, s_idx))
            x += space_width
        pending_space_indices = []

        # Lay out word characters.
        for idx_char in word_indices:
            c = text[idx_char]
            if c == "\t":
                c = " "
            c_width = font.getlength(c)
            layout.append((c, x, y, line_num, idx_char))
            x += c_width

    return layout, line_height


def create_video_frame_with_markup(display_text, display_chars, reveal_token_idx, active_token_idx, token_count, width, height, font_size=100):
    """Create a single video frame with prosigns, newlines, and info segments.

    - Timed Morse content is revealed up to reveal_token_idx (active token in red)
    - Prosigns are green once past (red when current)
    - Informational text in [brackets] is light-blue and appears instantly when reached
    - Explicit newlines are preserved
    """
    # Create black background
    img = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(img)
    
    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/calibri.ttf", font_size)
            except:
                font = ImageFont.load_default()
    
    padding = 40
    max_text_width = width - 2 * padding
    
    # Calculate layout for display text (supports explicit newlines)
    layout, line_height = get_wrapped_text_layout(display_text, font, max_text_width, padding, font_size)
    
    if not layout:
        return img
    
    # Calculate how many lines fit in viewport
    max_visible_lines = (height - 2 * padding) // line_height
    if max_visible_lines < 1:
        max_visible_lines = 1
    
    # Determine if this is the final frame
    show_all = (reveal_token_idx >= token_count and active_token_idx is None)
    
    # Find which line the active token (or last revealed token) is on (for scrolling)
    current_line_num = 0
    if layout:
        if show_all:
            current_line_num = max([ln for _, _, _, ln, _ in layout])
        else:
            focus_token_idx = active_token_idx
            if focus_token_idx is None and reveal_token_idx > 0:
                focus_token_idx = reveal_token_idx - 1

            # Prefer the first non-space char belonging to the current token
            found = False
            for char, _x, _y, ln, text_idx in layout:
                meta = display_chars[text_idx]
                if meta.get("is_info"):
                    continue
                t_idx = meta.get("token_idx")
                if focus_token_idx is not None and t_idx == focus_token_idx and char != " ":
                    current_line_num = ln
                    found = True
                    break
            if not found:
                # Fallback: last visible timed character
                for char, _x, _y, ln, text_idx in reversed(layout):
                    meta = display_chars[text_idx]
                    if meta.get("is_info"):
                        continue
                    t_idx = meta.get("token_idx")
                    if t_idx is not None and t_idx < reveal_token_idx and char != " ":
                        current_line_num = ln
                        break
    
    # Calculate scroll offset
    max_line = max([line_num for _, _, _, line_num, _ in layout]) if layout else 0
    scroll_offset = 0
    
    if (max_line + 1) > max_visible_lines:
        if current_line_num >= max_visible_lines:
            scroll_offset = current_line_num - max_visible_lines + 1
        if scroll_offset > max_line - max_visible_lines + 1:
            scroll_offset = max_line - max_visible_lines + 1
        if scroll_offset < 0:
            scroll_offset = 0
    
    start_y = padding - (scroll_offset * line_height)
    
    # Draw characters with proper colors
    for char, x_pos, y_offset, line_num, text_idx in layout:
        if char == ' ':
            continue
        
        if line_num < scroll_offset or line_num >= scroll_offset + max_visible_lines:
            continue
        
        if text_idx >= len(display_chars):
            continue

        meta = display_chars[text_idx]
        token_idx = meta.get("token_idx")
        is_prosign = meta.get("is_prosign", False)
        is_info = meta.get("is_info", False)
        info_anchor = meta.get("info_anchor")
        
        # Visibility rules
        if show_all:
            visible = True
        elif is_info:
            visible = info_anchor is not None and info_anchor <= reveal_token_idx
        else:
            visible = token_idx is not None and (token_idx < reveal_token_idx or token_idx == active_token_idx)

        if not visible:
            continue

        # Color rules
        if is_info:
            color = "#66CCFF"  # light blue
        elif show_all:
            color = "#00FF00" if is_prosign else "#FFFF00"
        else:
            if token_idx == active_token_idx:
                color = "#FF0000"
            else:
                color = "#00FF00" if is_prosign else "#FFFF00"

        y = start_y + y_offset
        draw.text((x_pos, y), char, fill=color, font=font)
    
    return img


def create_video_frame(text, current_index, width, height, font_size=100):
    """Create a single video frame showing text up to current_index with word wrapping and scrolling."""
    # Create black background
    img = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(img)
    
    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
        except:
            try:
                # Try other common fonts
                font = ImageFont.truetype("C:/Windows/Fonts/calibri.ttf", font_size)
            except:
                # Fallback to default font
                font = ImageFont.load_default()
    
    padding = 40
    max_text_width = width - 2 * padding
    
    # Calculate layout for full text (to know where characters should be)
    layout, line_height = get_wrapped_text_layout(text, font, max_text_width, padding, font_size)
    
    if not layout:
        return img
    
    # Calculate how many lines fit in viewport
    max_visible_lines = (height - 2 * padding) // line_height
    if max_visible_lines < 1:
        max_visible_lines = 1
    
    # Determine if this is the final frame (show all text)
    show_all = (current_index >= len(text))
    
    # Find which line the current character is on (or last line for final frame)
    current_line_num = 0
    if show_all:
        # For final frame, use the last line of text
        max_line = max([line_num for _, _, _, line_num, _ in layout]) if layout else 0
        current_line_num = max_line
    else:
        # Find the layout entry that matches current_index in the original text
        for char, x, y, line_num, text_idx in layout:
            if text_idx == current_index:
                current_line_num = line_num
                break
    
    # Calculate scroll offset - scroll up when current line would go below viewport
    max_line = max([line_num for _, _, _, line_num, _ in layout]) if layout else 0
    scroll_offset = 0
    
    # If text exceeds viewport height, implement scrolling
    if (max_line + 1) > max_visible_lines:
        # Start scrolling when current line would go below viewport
        if current_line_num >= max_visible_lines:
            scroll_offset = current_line_num - max_visible_lines + 1
        # Don't scroll past the end
        if scroll_offset > max_line - max_visible_lines + 1:
            scroll_offset = max_line - max_visible_lines + 1
        if scroll_offset < 0:
            scroll_offset = 0
    
    # Calculate starting y position with scroll offset
    start_y = padding - (scroll_offset * line_height)
    
    # Draw characters
    for char, x_pos, y_offset, line_num, text_idx in layout:
        # Skip spaces (they're invisible, just used for positioning)
        if char == ' ':
            continue
        
        # Only draw lines that are visible in viewport
        if line_num < scroll_offset or line_num >= scroll_offset + max_visible_lines:
            continue
        
        # For final frame, show all characters that are visible
        # For regular frames, show only up to current_index
        if show_all:
            # Final frame: show all characters that are visible in viewport
            # Only show characters that are actually in the text (text_idx < len(text))
            if text_idx < len(text):
                y = start_y + y_offset
                # All characters in final frame are past characters (yellow)
                color = '#FFFF00'  # Yellow for all text in final frame
                draw.text((x_pos, y), char, fill=color, font=font)
        else:
            # Regular frame: show only up to current_index
            # Use text_idx to match with current_index from original text
            if text_idx <= current_index:
                y = start_y + y_offset
                
                # Determine color
                if text_idx < current_index:
                    color = '#FFFF00'  # Yellow for past characters
                else:
                    color = '#FF0000'  # Red for current character
                
                draw.text((x_pos, y), char, fill=color, font=font)
    
    return img


def generate_video(text, output_file, effective_speed=18, character_speed=18):
    """Generate HD video with synchronized text and audio."""
    if not MOVIEPY_AVAILABLE:
        print("Error: moviepy and Pillow are required for video generation")
        sys.exit(1)
    
    print("Generating video...")
    print(f"Text: {text}")
    
    # Parse markup: timed morse tokens + display text + timeline events (includes pauses)
    tokens, display_chars, events = parse_markup(text, effective_speed=effective_speed, character_speed=character_speed)
    display_text = "".join([m["ch"] for m in display_chars])
    print(f"Display text: {display_text}")
    
    # Build timeline segments (token/pause) and total duration
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
    
    # Generate complete audio track from events (tokens + exact pauses)
    print("Generating audio track...")
    temp_audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_audio_file.close()
    
    audio_generator = generate_audio_from_events(events, effective_speed=effective_speed, character_speed=character_speed)
    with open(temp_audio_file.name, "wb") as f:
        import audiogen_p3
        audiogen_p3.write_wav(f, audio_generator)
    
    # Video dimensions (HD)
    width, height = 1920, 1080
    fps = 30
    font_size = 100  # Large font for phone viewing
    
    # Create frame generator function
    def make_frame(t):
        # Clamp time to valid range
        if t < 0:
            t = 0
        elif t >= total_duration:
            t = total_duration
        
        # Determine reveal + active token for time t.
        # During pauses: active_token_idx=None, reveal_token_idx does not change.
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
                # Segment fully completed
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
    
    # Create video clip
    print("Creating video frames...")
    video = VideoClip(make_frame, duration=total_duration)
    video = video.with_fps(fps)
    
    # Add audio
    print("Adding audio track...")
    audio = AudioFileClip(temp_audio_file.name)
    video = video.with_audio(audio)
    
    # Write video file
    print(f"Writing video to {output_file}...")
    video.write_videofile(output_file, fps=fps, codec='libx264', audio_codec='aac')
    
    # Cleanup
    video.close()
    audio.close()
    os.unlink(temp_audio_file.name)
    
    print(f"Video generation complete: {output_file}")


def read_input_file(filepath):
    """Read an input file and prepare for morse display.
    
    Preserves newlines (CR/LF) so they can be displayed as new lines in the viewport.
    Prosigns in angle brackets (e.g., <AR>, <SK>) and info segments in [brackets] are preserved.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    # Normalize CR to LF; universal newlines already converts CRLF/CR to \n in most cases.
    content = content.replace("\r", "\n")
    return content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Display text character by character with morse code audio')
    parser.add_argument('text', nargs='?', default=None, help='Text to display (omit when using -i)')
    parser.add_argument('-i', '--input-file', type=str, default=None,
                        help='Input file. Newlines/CR are preserved for display; prosigns in <angle brackets> supported; info segments in [brackets] are displayed instantly in light blue without timing/audio; commands in {braces} are not displayed (e.g. {p05} pauses for 5 seconds).')
    parser.add_argument('-v', '--video', action='store_true', help='Generate video file')
    parser.add_argument('-f', '--file', type=str, help='Output video filename (required with -v, or defaults to videos/morse_video.mp4)')
    parser.add_argument('--effective-speed', type=float, default=18,
                        help='Effective words per minute (Farnsworth speed). Default: 18')
    parser.add_argument('--character-speed', type=float, default=20,
                        help='Character speed in words per minute. Default: 20')
    
    args = parser.parse_args()
    
    if args.input_file:
        text = read_input_file(args.input_file)
    elif args.text is not None:
        text = args.text
    else:
        parser.error('Either provide text as argument or use -i/--input-file')
    
    # Do NOT uppercase globally: info segments in [brackets] must preserve case.
    
    if args.video:
        # Video generation mode
        if args.file:
            output_file = args.file
        else:
            # Default to videos/morse_video.mp4
            videos_dir = 'videos'
            os.makedirs(videos_dir, exist_ok=True)
            output_file = os.path.join(videos_dir, 'morse_video.mp4')
        
        # Ensure .mp4 extension
        if not output_file.endswith('.mp4'):
            output_file += '.mp4'
        
        # Create parent directories if needed
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        generate_video(text, output_file, effective_speed=args.effective_speed, character_speed=args.character_speed)
    else:
        # Terminal display mode (original behavior)
        display = ColorfulCharacterDisplay(text, effective_speed=args.effective_speed, character_speed=args.character_speed)
        if os.name == 'nt':
            # For Windows
            os.system('cls')
        else:
            # For UNIX-based systems (Linux, macOS)
            os.system('clear')

        time.sleep(3)
        more = True
        while more:
            more = display.next()

        time.sleep(3)
