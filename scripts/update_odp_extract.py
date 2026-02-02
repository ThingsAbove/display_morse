"""Extract video-title.odp to video-title_extracted and update video-title.zip.

Run this when slides/video-title.odp has been updated.
"""

import shutil
import zipfile
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent.parent
    slides_dir = project_root / "slides"
    odp_path = slides_dir / "video-title.odp"
    extracted_dir = slides_dir / "video-title_extracted"
    zip_path = slides_dir / "video-title.zip"

    if not odp_path.exists():
        print(f"Error: {odp_path} not found")
        return 1

    # Remove existing extracted directory
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir)

    # Extract ODP (it's a ZIP) to video-title_extracted
    extracted_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(odp_path, "r") as z:
        z.extractall(extracted_dir)

    # Copy ODP to video-title.zip
    shutil.copy2(odp_path, zip_path)

    print(f"Updated {extracted_dir} and {zip_path} from {odp_path}")
    return 0


if __name__ == "__main__":
    exit(main())
