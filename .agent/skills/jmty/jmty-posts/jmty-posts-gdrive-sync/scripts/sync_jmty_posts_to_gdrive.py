#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


COMMON_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "common" / "scripts"
if str(COMMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_SCRIPTS_DIR))

from runtime_common import detect_shared_root, get_repo_root, resolve_input_path


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _sync_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    source_entries = {entry.name: entry for entry in source.iterdir()}
    destination_entries = {entry.name: entry for entry in destination.iterdir()}

    for removed_name in sorted(destination_entries.keys() - source_entries.keys()):
        _remove_path(destination_entries[removed_name])

    for name, source_entry in source_entries.items():
        destination_entry = destination / name
        if source_entry.is_dir():
            if destination_entry.exists() and not destination_entry.is_dir():
                destination_entry.unlink()
            _sync_tree(source_entry, destination_entry)
            continue

        if destination_entry.exists() and destination_entry.is_dir():
            shutil.rmtree(destination_entry)
        destination_entry.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_entry, destination_entry)


def _default_destination_root() -> Path | None:
    explicit = os.environ.get("JMTY_GDRIVE_DEST_ROOT")
    if explicit:
        return resolve_input_path(explicit)

    shared_root = detect_shared_root()
    if shared_root is None:
        return None
    return shared_root / "outputs" / "jmty"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination_root", nargs="?")
    args = parser.parse_args()

    repo_root = get_repo_root()
    source_root = repo_root / "outputs" / "jmty"
    source_factory = source_root / "factory"
    source_remote = source_root / "remote"

    if not source_factory.exists():
        print(f"[ERROR] source not found: {source_factory}", file=sys.stderr)
        return 1

    if not source_remote.exists():
        print(f"[ERROR] source not found: {source_remote}", file=sys.stderr)
        return 1

    destination_root = (
        resolve_input_path(args.destination_root)
        if args.destination_root
        else _default_destination_root()
    )
    if destination_root is None:
        print(
            "[ERROR] destination root could not be detected. "
            "Pass a destination path or set TEAM_INFO_SHARED_ROOT / JMTY_GDRIVE_DEST_ROOT.",
            file=sys.stderr,
        )
        return 1

    destination_root.mkdir(parents=True, exist_ok=True)
    _sync_tree(source_factory, destination_root / "factory")
    _sync_tree(source_remote, destination_root / "remote")

    print("Synced successfully")
    print(f"- source: {source_factory} -> {destination_root / 'factory'}")
    print(f"- source: {source_remote} -> {destination_root / 'remote'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
