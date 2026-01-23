import os, time, sys
import argparse
import tempfile
import math
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

class ColorfulCharacterDisplay:
    def __init__(self, text):
        self.text = text
        self.index = 0

    def display_character(self, character):
        if os.name == 'nt':
            # For Windows
            os.system('cls')
        else:
            # For UNIX-based systems (Linux, macOS)
            os.system('clear')

        bright_yellow = "\033[1;33m"
        bright_red = "\033[1;31m"
        reset = "\033[0m"
        output = bright_yellow + self.text[:self.index] + bright_red + self.text[self.index] 
        print(output)

    def next(self):
        if self.index >= len(self.text):
            return False

        character = self.text[self.index]
        if character.isalnum():
            koch_audio = KochTrainerAudioGen(character, effective_speed=18, character_speed=20)
            koch_audio.emit_audio()
        else:
            koch_audio = KochTrainerAudioGen(' ', effective_speed=18, character_speed=20)
            koch_audio.emit_audio()
  
        self.display_character(character)
        self.index += 1
        return True


def calculate_character_duration(character, effective_speed=18, character_speed=20):
    """Calculate the audio duration for a single character in morse code.
    This must match exactly what KochTrainerAudioGen generates.
    
    IMPORTANT: generate_letter_sound() ALWAYS adds inter_letter*1.6 at the end,
    regardless of what comes next. This includes spaces too!
    
    Args:
        character: The character to calculate duration for
        effective_speed: Effective words per minute (Farnsworth speed)
        character_speed: Character speed in words per minute
    """
    # Create a temporary audio generator to get timing info and access methods
    koch_audio = KochTrainerAudioGen(character, effective_speed=effective_speed, character_speed=character_speed)
    
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
    if character == ' ':
        return inter_word + (inter_letter * 1.6)
    
    # Count dits and dahs in the pattern
    if character not in koch_audio._letters:
        # Unknown character, use default inter-letter gap
        # generate_letter_sound() always adds inter_letter at the end
        return inter_letter * 1.6
    
    pattern = koch_audio._letters[character]
    num_symbols = len(pattern)
    
    # Calculate duration: symbols + inter-symbol gaps + inter-letter gap
    # This matches generate_letter_sound() which ALWAYS creates:
    # [tone1, inter_symbol, tone2, inter_symbol, ..., toneN, inter_letter*1.6]
    # The inter_letter gap is ALWAYS added, even if the next character is a space
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
    
    # Calculate timing for each character
    print("Calculating character timings...")
    character_timings = []
    current_time = 0.0
    
    for i, char in enumerate(text):
        # Calculate duration - generate_letter_sound() always adds inter_letter*1.6
        # at the end, regardless of what comes next
        duration = calculate_character_duration(char, effective_speed, character_speed)
        character_timings.append({
            'index': i,
            'character': char,
            'start_time': current_time,
            'duration': duration,
            'end_time': current_time + duration
        })
        current_time += duration
    
    total_duration = current_time
    print(f"Total duration: {total_duration:.2f} seconds")
    
    # Generate complete audio track
    print("Generating audio track...")
    temp_audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_audio_file.close()
    
    full_audio = KochTrainerAudioGen(text, effective_speed=effective_speed, character_speed=character_speed)
    full_audio.save_file(temp_audio_file.name)
    
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
        
        # Find which character should be displayed at time t
        current_index = 0
        for timing in character_timings:
            if t >= timing['start_time']:
                current_index = timing['index']
            else:
                break
        
        # For final frame (at or past end), set current_index to len(text) to indicate "show all"
        # This tells create_video_frame to show all visible text in the viewport
        if t >= total_duration:
            current_index = len(text)  # One past the end indicates final frame
        
        # Create frame
        frame_img = create_video_frame(text, current_index, width, height, font_size)
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
        
        generate_video(text, output_file)
    else:
        # Terminal display mode (original behavior)
        display = ColorfulCharacterDisplay(text)
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
