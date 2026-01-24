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
        # Parse prosigns and get tokenized version
        self.tokens, self.display_text = parse_prosigns(text.upper())
        self.token_index = 0
        self.effective_speed = effective_speed
        self.character_speed = character_speed
        
        # Track which tokens are prosigns for green display
        temp_gen = KochTrainerAudioGen("", effective_speed=effective_speed, character_speed=character_speed)
        self.valid_prosigns = {k for k in temp_gen._letters.keys() if len(k) > 1}
        
        # Build character index mapping for display
        self.char_to_token = []
        char_idx = 0
        for token in self.tokens:
            if token in self.valid_prosigns:
                # Prosign - map each character to this token index
                for _ in range(len(token)):
                    self.char_to_token.append(self.token_index)
                char_idx += len(token)
            else:
                # Regular character
                self.char_to_token.append(self.token_index)
                char_idx += 1
            self.token_index += 1
        self.token_index = 0

    def is_prosign(self, token):
        """Check if a token is a prosign."""
        return token in self.valid_prosigns

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
        reset = "\033[0m"
        
        # Build output with proper colors
        output_parts = []
        
        # Past tokens (before current)
        for i in range(self.token_index):
            token = self.tokens[i]
            if self.is_prosign(token):
                output_parts.append(bright_green + token)
            else:
                output_parts.append(bright_yellow + token)
        
        # Current token
        if self.token_index < len(self.tokens):
            current_token = self.tokens[self.token_index]
            output_parts.append(bright_red + current_token)
        
        output = ''.join(output_parts) + reset
        print(output)

    def next(self):
        if self.token_index >= len(self.tokens):
            return False

        token = self.tokens[self.token_index]
        
        # Send token to KochTrainerAudioGen
        # For prosigns, send the entire prosign string
        # For regular characters, send as-is
        koch_audio = KochTrainerAudioGen(token, effective_speed=self.effective_speed, character_speed=self.character_speed)
        koch_audio.emit_audio()
  
        self.display_character()
        self.token_index += 1
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


def get_wrapped_text_layout(text, font, max_width, padding=40, font_size=100):
    """Calculate character positions with word wrapping.
    Returns list of (char, x, y, line_num, text_index) tuples.
    Includes all characters from text, preserving exact index mapping."""
    layout = []
    x = padding
    y = 0
    line_num = 0
    line_height = int(font_size * 1.3)
    current_line_width = 0
    
    # Split into words for word wrapping, but track original indices
    words_with_indices = []
    i = 0
    while i < len(text):
        # Skip spaces
        while i < len(text) and text[i] == ' ':
            i += 1
        if i >= len(text):
            break
        
        # Get word
        word_start = i
        word = []
        while i < len(text) and text[i] != ' ':
            word.append((text[i], i))
            i += 1
        
        if word:
            words_with_indices.append((word, word_start))
    
    # Process words with word wrapping
    for word_idx, (word_chars, word_start) in enumerate(words_with_indices):
        word = ''.join([char for char, _ in word_chars])
        
        # Check if we need a space before this word (not first word)
        if word_idx > 0:
            space_width = font.getlength(' ')
            # Check if adding space + word would exceed width
            if current_line_width + space_width + font.getlength(word) > (max_width - 2 * padding):
                # Move to next line
                line_num += 1
                y += line_height
                x = padding
                current_line_width = 0
            else:
                # Add space on current line
                # Find the space before this word in the original text
                space_idx = word_start - 1
                if space_idx >= 0 and text[space_idx] == ' ':
                    layout.append((text[space_idx], x, y, line_num, space_idx))
                x += space_width
                current_line_width += space_width
        
        # Add characters of the word
        for char, char_idx in word_chars:
            char_width = font.getlength(char)
            layout.append((char, x, y, line_num, char_idx))
            x += char_width
            current_line_width += char_width
    
    return layout, line_height


def create_video_frame_with_tokens(display_text, tokens, char_positions, current_token_idx, width, height, font_size=100, valid_prosigns=None):
    """Create a single video frame showing text with prosign support.
    
    Args:
        display_text: Text to display (prosigns without angle brackets)
        tokens: List of tokens (characters and prosigns)
        char_positions: List of dicts mapping each character to its token info
        current_token_idx: Index of current token being displayed
        width, height: Video dimensions
        font_size: Font size
        valid_prosigns: Set of valid prosign strings
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
    
    # Calculate layout for display text
    layout, line_height = get_wrapped_text_layout(display_text, font, max_text_width, padding, font_size)
    
    if not layout:
        return img
    
    # Calculate how many lines fit in viewport
    max_visible_lines = (height - 2 * padding) // line_height
    if max_visible_lines < 1:
        max_visible_lines = 1
    
    # Determine if this is the final frame
    show_all = (current_token_idx >= len(tokens))
    
    # Find which line the current character is on
    current_line_num = 0
    if show_all:
        max_line = max([line_num for _, _, _, line_num, _ in layout]) if layout else 0
        current_line_num = max_line
    else:
        # Find the first character of the current token
        current_char_idx = 0
        for i, pos in enumerate(char_positions):
            if pos['token_idx'] == current_token_idx:
                current_char_idx = i
                break
        
        # Find the layout entry for this character
        for char, x, y, line_num, text_idx in layout:
            if text_idx == current_char_idx:
                current_line_num = line_num
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
        
        if text_idx >= len(char_positions):
            continue
        
        pos_info = char_positions[text_idx]
        token_idx = pos_info['token_idx']
        is_prosign = pos_info['is_prosign']
        
        if show_all:
            # Final frame: show all characters
            if text_idx < len(display_text):
                y = start_y + y_offset
                # Determine color based on whether it's a prosign
                if is_prosign and valid_prosigns:
                    color = '#00FF00'  # Green for prosigns
                else:
                    color = '#FFFF00'  # Yellow for regular characters
                draw.text((x_pos, y), char, fill=color, font=font)
        else:
            # Regular frame: show up to current token
            if token_idx < current_token_idx:
                # Past token
                y = start_y + y_offset
                if is_prosign and valid_prosigns:
                    color = '#00FF00'  # Green for past prosigns
                else:
                    color = '#FFFF00'  # Yellow for past regular characters
                draw.text((x_pos, y), char, fill=color, font=font)
            elif token_idx == current_token_idx:
                # Current token
                y = start_y + y_offset
                color = '#FF0000'  # Red for current token
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
    
    # Parse prosigns to get tokens and display text
    tokens, display_text = parse_prosigns(text.upper())
    print(f"Tokens: {tokens}")
    print(f"Display text: {display_text}")
    
    # Get valid prosigns for color tracking
    temp_gen = KochTrainerAudioGen("", effective_speed=effective_speed, character_speed=character_speed)
    valid_prosigns = {k for k in temp_gen._letters.keys() if len(k) > 1}
    
    # Calculate timing for each token
    print("Calculating token timings...")
    token_timings = []
    current_time = 0.0
    
    # Build character index mapping for display
    char_to_token = []
    char_positions = []  # Track which characters belong to which token
    char_idx = 0
    for token_idx, token in enumerate(tokens):
        token_start_char = char_idx
        if token in valid_prosigns:
            # Prosign - each character maps to this token
            for _ in range(len(token)):
                char_to_token.append(token_idx)
                char_positions.append({
                    'token_idx': token_idx,
                    'is_prosign': True,
                    'char_in_token': char_idx - token_start_char
                })
                char_idx += 1
        else:
            # Regular character
            char_to_token.append(token_idx)
            char_positions.append({
                'token_idx': token_idx,
                'is_prosign': False,
                'char_in_token': 0
            })
            char_idx += 1
        
        # Calculate duration for this token
        duration = calculate_token_duration(token, effective_speed, character_speed)
        token_timings.append({
            'token_idx': token_idx,
            'token': token,
            'start_time': current_time,
            'duration': duration,
            'end_time': current_time + duration,
            'is_prosign': token in valid_prosigns
        })
        current_time += duration
    
    total_duration = current_time
    print(f"Total duration: {total_duration:.2f} seconds")
    
    # Generate complete audio track from tokens
    print("Generating audio track...")
    temp_audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_audio_file.close()
    
    # Generate audio from tokens
    audio_generator = generate_audio_from_tokens(tokens, effective_speed=effective_speed, character_speed=character_speed)
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
        
        # Find which token should be displayed at time t
        current_token_idx = 0
        for timing in token_timings:
            if t >= timing['start_time']:
                current_token_idx = timing['token_idx']
            else:
                break
        
        # For final frame (at or past end), set current_token_idx to len(tokens) to indicate "show all"
        if t >= total_duration:
            current_token_idx = len(tokens)  # One past the end indicates final frame
        
        # Create frame with token information
        frame_img = create_video_frame_with_tokens(
            display_text, tokens, char_positions, current_token_idx, 
            width, height, font_size, valid_prosigns
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Display text character by character with morse code audio')
    parser.add_argument('text', help='Text to display')
    parser.add_argument('-v', '--video', action='store_true', help='Generate video file')
    parser.add_argument('-f', '--file', type=str, help='Output video filename (required with -v, or defaults to videos/morse_video.mp4)')
    parser.add_argument('--effective-speed', type=float, default=18,
                        help='Effective words per minute (Farnsworth speed). Default: 18')
    parser.add_argument('--character-speed', type=float, default=20,
                        help='Character speed in words per minute. Default: 20')
    
    args = parser.parse_args()
    
    text = args.text.upper()
    
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
