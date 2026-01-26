# Display Morse Code Trainer

A Python tool for displaying text character-by-character with synchronized Morse code audio, supporting both terminal display and video generation.

## Features

### Core Functionality
- **Character-by-character display**: Text is revealed progressively as Morse code is played
- **Synchronized audio**: Each character is accompanied by its Morse code audio
- **Color-coded display**:
  - **Red**: Current character being played
  - **Yellow**: Past regular characters
  - **Green**: Past prosigns (special Morse sequences)
  - **Light Blue**: Informational text (not converted to Morse)

### Advanced Markup Support

#### Prosigns (`<...>`)
Special Morse code sequences enclosed in angle brackets are converted to their prosign equivalents:
- Examples: `<AR>`, `<SK>`, `<BT>`, `<KN>`
- Displayed in green once past
- Fully timed and sounded in Morse code

#### Informational Text (`[...]`)
Text in square brackets is displayed instantly without Morse conversion:
- **Not converted to Morse code** (no audio/timing)
- **Case preserved** (not uppercased)
- **Brackets are not displayed** (only the content inside)
- **Appears in light blue** when reached
- Example: `[Operator note: slower here]` → displays as "Operator note: slower here" in light blue

#### Commands (`{...}`)
Commands in braces are not displayed but affect playback:
- **`{p##}`**: Pause command
  - `{p05}` pauses for 5 seconds
  - `{p2}` pauses for 2 seconds
  - `{p2.5}` pauses for 2.5 seconds
  - Case-insensitive: `{P05}` works the same
  - During pause: video timeline advances, but no new Morse characters are revealed
  - Audio includes exact-length silence

#### Newlines
- **Carriage returns and newlines are preserved** in the display
- Each newline is **timed as a space** in Morse code (creates a pause)
- Words **do not wrap mid-word**; if a word won't fit, it starts on the next line

## Command Line Options

### Basic Usage

```bash
# Display text directly in terminal
python display.py "HELLO WORLD"

# Read from a file
python display.py -i input.txt

# Generate video file
python display.py -i input.txt -v

# Generate video with custom output filename
python display.py -i input.txt -v -f output_video.mp4
```

### Arguments

| Option | Description |
|--------|-------------|
| `text` | Text to display (optional if using `-i`) |
| `-i, --input-file` | Input file path. Newlines/CR are preserved; supports prosigns `<...>`, info segments `[...]`, and commands `{...}` |
| `-v, --video` | Generate video file instead of terminal display |
| `-f, --file` | Output video filename (required with `-v`, or defaults to `videos/morse_video.mp4`) |
| `--effective-speed` | Effective words per minute (Farnsworth speed). Default: 18 |
| `--character-speed` | Character speed in words per minute. Default: 20 |
| `-h, --help` | Show help message |

### Examples

```bash
# Terminal display with default speeds
python display.py "CQ CQ DE W1AW K"

# Terminal display from file
python display.py -i sample.txt

# Generate video with custom speeds
python display.py -i sample.txt -v --effective-speed 15 --character-speed 20

# Generate video with custom output path
python display.py -i sample.txt -v -f "videos/my_video.mp4"

# Complex example with all features
python display.py -i "input.txt" -v --effective-speed 18 --character-speed 22 -f "output.mp4"
```

## Libraries and Dependencies

### Required Libraries

- **audiogen-p3**: Morse code audio generation
- **koch_trainer**: Local module providing `KochTrainerAudioGen` class

### Optional Libraries (for video generation)

- **moviepy**: Video file creation and editing
- **Pillow (PIL)**: Image processing for video frames
- **numpy**: Numerical operations for video processing
- **imageio-ffmpeg**: FFmpeg backend for video encoding

### Installation

Install dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

**Note**: If video generation libraries are not installed, `display.py` will still work for terminal display mode, but video generation will be unavailable.

## Input File Format

Input files support plain text with special markup:

```
CQ CQ DE W1AW <AR>
[Operator: Starting transmission]
Hello World {p05}
[Pause complete]
<SK>
```

- **Plain text**: Converted to Morse code
- **`<AR>`**: Prosign (sounded in Morse, displayed in green)
- **`[Operator: ...]`**: Info text (light blue, no Morse, brackets not shown)
- **`{p05}`**: 5-second pause (not displayed)

## Output Modes

### Terminal Display Mode
- Character-by-character display with color coding
- Synchronized audio playback
- 3-second delay before and after playback
- Supports all markup features

### Video Generation Mode
- HD video output (1920x1080)
- 30 FPS
- Synchronized audio track
- Text scrolling when content exceeds viewport
- Large font size (100pt) optimized for phone viewing
- Output format: MP4 (H.264 video, AAC audio)

## Technical Details

- **Word wrapping**: Words never break mid-word; entire words move to next line if needed
- **Timing accuracy**: Pause commands use exact-second durations without affecting Morse timing
- **Character encoding**: UTF-8 support for international characters
- **Platform support**: Works on Windows, Linux, and macOS

## See Also

- `koch_trainer.py`: Koch method training tool with random character/word generation
- `requirements.txt`: Complete list of Python dependencies
