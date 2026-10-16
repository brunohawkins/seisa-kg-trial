"""SUMMARY: Turns the Seisa brief documents into plain text files.

It reads every PDF and Word (.docx) file in the `brief/` folder and writes a
matching .txt file into `docs/brief_text/`, so the brief can be searched and
quoted easily. PDFs are split into pages, with a marker line before each one,
so any quote can be traced back to its page.

Both folders are kept out of git (decision D-011), because the brief is
Seisa's material.

Run it with:  uv run python scripts/extract_brief.py
"""

# A tidy way of working with file and folder paths.
from pathlib import Path

# The PDF-reading library.
import pymupdf

# The Word-document-reading library (it installs under the name "docx").
import docx

# The project's top folder: this script's folder ("scripts"), then one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Where the original brief documents live.
BRIEF_DIR = PROJECT_ROOT / "brief"
# Where the text versions will be written.
OUTPUT_DIR = PROJECT_ROOT / "docs" / "brief_text"


# Read every page of one PDF and return all its text as one string.
def pdf_to_text(path: Path) -> str:
    # Open the PDF; the "with" block closes it again automatically afterwards.
    with pymupdf.open(path) as document:
        # Start an empty list to collect each page's text.
        pages = []
        # Go through the pages one at a time, counting from 1 for humans.
        for page_number, page in enumerate(document, start=1):
            # Add a marker line saying which page follows, then that page's text.
            pages.append(f"=== Page {page_number} ===\n{page.get_text()}")
    # Join all the pages together, with a blank line between each.
    return "\n\n".join(pages)


# Read one Word document and return its text, one paragraph per line.
def docx_to_text(path: Path) -> str:
    # Open the Word document.
    document = docx.Document(path)
    # Take each paragraph's text and join them with line breaks.
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


# The main job: convert every brief document and report what was done.
def main() -> None:
    # Create the output folder if it isn't there yet (no error if it already is).
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Go through every file in the brief folder, in alphabetical order.
    for source in sorted(BRIEF_DIR.iterdir()):
        # Look at the file's ending in lower case (".pdf", ".docx", ...).
        suffix = source.suffix.lower()
        # If it's a PDF, use the PDF reader.
        if suffix == ".pdf":
            # Get the PDF's text.
            text = pdf_to_text(source)
        # If it's a Word document, use the Word reader.
        elif suffix == ".docx":
            # Get the Word document's text.
            text = docx_to_text(source)
        # Anything else (e.g. hidden system files) is skipped.
        else:
            # Move straight on to the next file.
            continue
        # Build the output file name: same name, ending in .txt instead.
        target = OUTPUT_DIR / (source.stem + ".txt")
        # Save the text, using UTF-8 so special characters like "·" survive.
        target.write_text(text, encoding="utf-8")
        # Tell the person running the script what was written, and how big it is.
        print(f"Wrote {target.relative_to(PROJECT_ROOT)} ({len(text):,} characters)")


# Only run main() when this file is run directly, not when it's imported.
if __name__ == "__main__":
    # Start the main job.
    main()
