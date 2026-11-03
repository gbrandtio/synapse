"""Download the bundled models and check them against packaging/models.lock.yaml.

Run: uv run --no-project --with pyyaml==6.0.3 packaging/fetch_models.py <models folder> [<copy to>]

Files already there with the right hash are kept, so this is quick to run again. A wrong hash
stops with an error, so a build cannot silently pick up a different model. With a second folder,
exactly the pinned files are copied there, so nothing stray reaches the app.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

import yaml

LOCK = Path(__file__).with_name("models.lock.yaml")
CHUNK = 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    partial = target.with_name(target.name + ".partial")
    # Hosts here are fixed in the lock file, which is reviewed like code.
    try:
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as file:  # noqa: S310
            while chunk := response.read(CHUNK):
                file.write(chunk)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def main(folder: Path, copy_to: Path | None) -> None:
    lock = yaml.safe_load(LOCK.read_text())
    for entry in lock["files"]:
        target = folder / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha256(target) != entry["sha256"]:
            print(f"Downloading {target.name}", flush=True)
            download(entry["url"], target)
        if sha256(target) != entry["sha256"]:
            target.unlink()
            sys.exit(f"Wrong hash for {target.name}. It was not what the lock file pins.")
    # FastEmbed finds the snapshot through this file.
    embedding = lock["embedding"]
    ref = folder / embedding["ref_file"]
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(embedding["revision"])
    print("All models match the lock file.")
    if copy_to:
        for path in [*(e["path"] for e in lock["files"]), embedding["ref_file"]]:
            (copy_to / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(folder / path, copy_to / path)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
