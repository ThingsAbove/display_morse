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

## Project Structure

- **display.py** — Core display logic, markup parsing, morse timing, and frame rendering. Entry point for CLI.
- **video_creation.py** — Video generation: morse content assembly, title slide (ODP), intro clips, and output.
- **video_effects.py** — Video effects (e.g., Ken Burns logo intro).
- **koch_trainer.py** — Koch method training and morse audio generation.
- **scripts/update_odp_extract.py** — Re-extract ODP template to video-title_extracted and video-title.zip.

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
| `--title` | Title for video intro slide (enables title + logo intro when `-v`) |
| `--subtitle` | Subtitle for video intro slide |
| `--detailtitle` | Details text for video intro slide |
| `--intro-length-duration` | Seconds to hold full logo after Ken Burns pan. Default: 15 |
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

# Generate video with title slide and logo intro
python display.py -i input.txt -v -f output.mp4 --title "Lesson 1" --subtitle "Letters A–E" --detailtitle "Koch Method"
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

### LibreOffice (for title slide intro)

When using `--title` to add a title slide intro, **LibreOffice** must be installed with `soffice` on your PATH (or in `C:\Program Files\LibreOffice` on Windows). The tool uses LibreOffice headless to render the ODP template (`slides/video-title.odp`) to PNG. It runs with `--nofirststartwizard` and an isolated profile to avoid first-run dialogs, and retries on failure. On Windows, it invokes `soffice.com` with `CREATE_NO_WINDOW` to prevent console popups from blocking the process.

### Test Dependencies

- **pytest**: Test framework for CLI and video effect tests.
- **pytest-timeout**: Ensures the title slide non-interactive test fails fast if it hangs.

### Installation

Install dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

**Note**: If video generation libraries are not installed, `display.py` will still work for terminal display mode, but video generation will be unavailable.

## Running Tests

```bash
pytest tests/ -v
```

Run specific test files:

```bash
pytest tests/test_cli_args.py -v
pytest tests/test_ken_burns.py -v
pytest tests/test_title_slide.py -v
```

`test_title_slide.py` verifies that title slide generation completes without interactive prompts (requires LibreOffice and `slides/video-title.odp`). It times out after 120 seconds if blocked.

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

### Video Title and Intro (with `--title`)

When `--title` is provided with `-v`, the generated video includes:

1. **Title slide** (3 seconds): Rendered from `slides/video-title.odp` with TITLE, SUBTITLE, and DETAILS placeholders replaced. 1 second fade in. Font size and color from the template are preserved.
2. **Logo intro** (8 second pan + `--intro-length-duration` hold): Ken Burns effect panning across `images/logo.png` left to right (aspect ratio preserved), 1 second fade in and 1.5 second fade out.
3. **Morse content**: Main video.
4. **End roll** (8 second pan + 10 second hold): Duplicate Ken Burns logo with 1 second fade in and 3 second fade out.

## Technical Details

- **Word wrapping**: Words never break mid-word; entire words move to next line if needed
- **Timing accuracy**: Pause commands use exact-second durations without affecting Morse timing
- **Character encoding**: UTF-8 support for international characters
- **Platform support**: Works on Windows, Linux, and macOS

## Updating the Title Slide Template

After editing `slides/video-title.odp`, run:

```bash
python scripts/update_odp_extract.py
```

This updates `slides/video-title_extracted/` and `slides/video-title.zip` from the ODP.

## See Also

- `koch_trainer.py`: Koch method training tool with random character/word generation
- `video_creation.py`: Video generation and title/intro assembly
- `video_effects.py`: Ken Burns and other video effects
- `tests/`: Test suite for CLI and effects
- `requirements.txt`: Complete list of Python dependencies
