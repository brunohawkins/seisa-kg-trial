"""SUMMARY: Builds the handoff zip for Seisa (D-126): everything someone needs
to read every result without running anything, or to rebuild both graphs
identically without any API key.

What goes in (inside one folder, seisa-kg-trial/):
- every file git holds at the last commit (code, docs, tests, config);
- data/raw/ (every download and every Gemini answer, cached), data/interim/
  (the fact list, the sentences, the extracted facts) and data/output/ (the
  RDF graph file, the answers, the comparison's attempts).

What stays out: .env (the keys), brief/ and its text copies (Seisa's own
material, D-011), tools/ and data/neo4j/ (the Neo4j program and database,
rebuilt by `make neo4j-install` and the build), .venv/.

It refuses to run if there are changes not yet committed, so the zip always
matches a commit. After writing the zip it checks every file in it for the
values in .env (never printing them) and for paths that must stay out; if any
is found, the zip is deleted and the run fails.

Output: data/handoff/seisa-kg-trial-<date>-<commit>.zip (data/ isn't in git).
Run with: make handoff
"""

# Runs git.
import subprocess
# Stops with an error message.
import sys
# Reads and writes zip files.
import zipfile
# Today's date, for the file name.
from datetime import date
# A tidy way of working with file paths.
from pathlib import Path

# The project's top folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Where the zip is written (inside data/, which git ignores).
OUT_DIR = PROJECT_ROOT / "data" / "handoff"
# The data folders that go in.
DATA_DIRS = ("data/raw", "data/interim", "data/output")
# Paths that must never be in the zip.
FORBIDDEN = (".env", "brief/", "docs/brief_text/", "tools/", "data/neo4j/", ".venv/", "data/handoff/")
# The secret settings whose values must never appear in any file.
SECRET_KEYS = ("LLM_API_KEY", "COMPANIES_HOUSE_API_KEY", "NEO4J_PASSWORD")


# Run a git command in the project and return what it prints.
def git(*args: str) -> str:
    # Run it, stopping if git reports an error.
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout


# The secret values from .env (never printed), skipping any too short to search for safely.
def secret_values() -> dict[str, bytes]:
    # The values found.
    found = {}
    # Each line of .env.
    for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        # A "NAME=value" line, not a comment.
        if "=" in line and not line.lstrip().startswith("#"):
            # Split into the name and the value.
            name, value = line.split("=", 1)
            # Without spaces or quote marks around it.
            value = value.strip().strip('"').strip("'")
            # One of the secrets, long enough to search for.
            if name.strip() in SECRET_KEYS and len(value) >= 6:
                # Remember it as bytes, to search inside any file.
                found[name.strip()] = value.encode("utf-8")
    # The secrets.
    return found


# Build the zip, check it, and say where it is.
def main() -> None:
    # Any change not yet committed: stop, so the zip always matches a commit.
    if git("status", "--porcelain").strip():
        # Say why.
        sys.exit("Commit your changes first: the zip must match a commit.")
    # The commit's short name, e.g. "bcf6a0a".
    commit = git("rev-parse", "--short", "HEAD").strip()
    # Make the output folder if needed.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # The zip's path, e.g. data/handoff/seisa-kg-trial-2026-10-21-bcf6a0a.zip.
    out = OUT_DIR / f"seisa-kg-trial-{date.today().isoformat()}-{commit}.zip"
    # Every file git holds at this commit.
    files = [f for f in git("ls-files").splitlines() if f]
    # Plus every file in the data folders.
    files += sorted(str(p.relative_to(PROJECT_ROOT)) for d in DATA_DIRS for p in (PROJECT_ROOT / d).rglob("*") if p.is_file())
    # Write the zip, every file inside one top folder.
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        # Each file.
        for f in files:
            # Skip macOS's folder-settings files.
            if Path(f).name != ".DS_Store":
                # Add it under seisa-kg-trial/.
                z.write(PROJECT_ROOT / f, f"seisa-kg-trial/{f}")
    # The check: the secrets' values, and the paths that must stay out.
    secrets = secret_values()
    # Problems found (described without ever showing a secret).
    problems = []
    # Read the zip back.
    with zipfile.ZipFile(out) as z:
        # Each file in it.
        for name in z.namelist():
            # Its path inside the project.
            inner = name.removeprefix("seisa-kg-trial/")
            # A path that must stay out: a folder by its start, a file by its exact name (so .env.example, the safe template, stays in).
            if any(inner.startswith(f) if f.endswith("/") else inner == f for f in FORBIDDEN):
                # Note it.
                problems.append(f"forbidden path: {inner}")
            # Its contents.
            content = z.read(name)
            # Each secret.
            for key, value in secrets.items():
                # Found inside this file: name the setting and the file, never the value.
                if value in content:
                    # Note it.
                    problems.append(f"the value of {key} appears in {inner}")
        # How many files.
        count = len(z.namelist())
    # Anything wrong: delete the zip and stop.
    if problems:
        # Delete it.
        out.unlink()
        # Say what was wrong.
        sys.exit("Handoff zip NOT made:\n  " + "\n  ".join(problems))
    # Say what was made.
    print(f"Wrote {out.relative_to(PROJECT_ROOT)}: {count} files, {out.stat().st_size / 1e6:.1f} MB, commit {commit}.")
    # And that the check passed.
    print(f"Checked: no forbidden paths; none of the {len(secrets)} secret values from .env appears in any file.")


# Run main() when this file is run directly.
if __name__ == "__main__":
    # Go.
    main()
