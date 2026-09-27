#!/usr/bin/env python3
"""
Bridge skills from external agent directories into the current Codex session.

Commands:
    search <name>   - Find a skill by name across known skill directories
    link <src>      - Symlink an external skill into ~/.codex/skills
    unlink <name>   - Remove a bridged skill (removes symlink only)
    list            - List all currently bridged (symlinked) skills
"""

import os
import shutil
import sys
from pathlib import Path


def codex_skills_dir() -> Path:
    """Return the target Codex skills directory."""
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "skills"
    return Path.home() / ".codex" / "skills"


def search_dirs() -> list[Path]:
    """Return directories to search for skills."""
    dirs: list[Path] = []
    candidates = [
        Path.home() / ".codex" / "skills",
        Path.home() / ".agents" / "skills",
    ]
    # Add workspace-local skill directories from environment
    for root in os.environ.get("WORKSPACE_ROOTS", "").split(os.pathsep):
        root = root.strip()
        if not root:
            continue
        p = Path(root)
        candidates.append(p / ".codex" / "skills")
        candidates.append(p / ".agents" / "skills")

    seen: set[Path] = set()
    for d in candidates:
        resolved = d.resolve() if d.exists() else d
        if resolved not in seen:
            seen.add(resolved)
            dirs.append(d)
    return dirs


def find_skill(name: str) -> list[Path]:
    """Search for a skill folder matching name across all known directories."""
    results: list[Path] = []
    for base in search_dirs():
        if not base.exists():
            continue
        candidate = base / name
        if candidate.is_dir() and (candidate / "SKILL.md").exists():
            results.append(candidate)
    return results


def cmd_search(name: str) -> int:
    results = find_skill(name)
    if not results:
        print(f"No skill named '{name}' found in any known directory.")
        print("\nSearched:")
        for d in search_dirs():
            print(f"  {d}")
        return 1
    print(f"Found '{name}':")
    for r in results:
        target = codex_skills_dir() / name
        already = " [BRIDGED]" if target.is_symlink() and target.resolve() == r.resolve() else ""
        print(f"  {r}{already}")
    return 0


def cmd_link(src_str: str) -> int:
    src = Path(src_str).expanduser().resolve()
    if not src.exists():
        print(f"Source does not exist: {src}")
        return 1
    if not (src / "SKILL.md").exists():
        print(f"Not a valid skill (missing SKILL.md): {src}")
        return 1

    target = codex_skills_dir() / src.name
    codex_skills_dir().mkdir(parents=True, exist_ok=True)

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            print(f"Replacing existing symlink: {target} -> {target.resolve()}")
            target.unlink()
        else:
            print(f"ERROR: '{target.name}' already exists as a real directory. Remove it manually to avoid data loss.")
            return 1

    try:
        target.symlink_to(src)
    except OSError:
        # Cross-volume fallback: copy
        print(f"Symlink failed (cross-volume?). Copying instead...")
        shutil.copytree(src, target)

    print(f"Bridged: {src.name}")
    print(f"  source: {src}")
    print(f"  target: {target}")
    return 0


def cmd_unlink(name: str) -> int:
    target = codex_skills_dir() / name
    if not target.exists() and not target.is_symlink():
        print(f"No bridged skill '{name}' found.")
        return 1
    if target.is_symlink():
        target.unlink()
        print(f"Removed symlink: {name}")
    elif target.is_dir():
        print(f"Refusing to remove real directory: {target}")
        return 1
    return 0


def cmd_list() -> int:
    base = codex_skills_dir()
    if not base.exists():
        print("No codex skills directory found.")
        return 0

    bridged = []
    for item in sorted(base.iterdir()):
        if item.is_symlink():
            try:
                dest = item.resolve()
                bridged.append((item.name, dest))
            except OSError:
                bridged.append((item.name, None))

    if not bridged:
        print("No bridged skills currently.")
        return 0

    print("Bridged skills:")
    for name, dest in bridged:
        status = str(dest) if dest else "[broken symlink]"
        print(f"  {name} -> {status}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]; args = argv[2:]
    if cmd == "search":
        if not args:
            print("Usage: bridge.py search <name>")
            return 1
        return cmd_search(args[0])
    if cmd == "link":
        if not args:
            print("Usage: bridge.py link <source-path>")
            return 1
        return cmd_link(args[0])
    if cmd == "unlink":
        if not args:
            print("Usage: bridge.py unlink <name>")
            return 1
        return cmd_unlink(args[0])
    if cmd == "list":
        return cmd_list()
    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
