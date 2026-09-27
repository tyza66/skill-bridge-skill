#!/usr/bin/env python3
"""
Bridge skills from external agent directories into the current Codex session.

Cross-platform: Linux, macOS, Windows (symlinks with junction/copy fallback)
Cross-agent:   Codex, Agents, Claude Code, Cursor, Windsurf, plus custom sources

Commands:
    search <name>            Find a skill by name across known directories
    link <src> [-c] [-f]     Bridge an external skill into ~/.codex/skills
    unlink <name>            Remove a bridged skill (symlink or copy marker)
    list                     List all currently bridged skills
    sources [add|list|remove <path>]   Manage custom skill source directories
                              (edit ~/.codex/skill-bridge/sources)
"""

import json
import os
import platform
import shutil
import sys
from pathlib import Path

import struct

try:
    import ctypes
    from ctypes import wintypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def codex_skills_dir() -> Path:
    """Target Codex skills directory."""
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "skills"
    return Path.home() / ".codex" / "skills"


def bridge_config_dir() -> Path:
    """Directory for bridge config (custom sources, copy markers)."""
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home) if codex_home else Path.home() / ".codex"
    return base / "skill-bridge"


def custom_sources_file() -> Path:
    return bridge_config_dir() / "sources.json"


# ---------------------------------------------------------------------------
# Known skill directories (cross-agent)
# ---------------------------------------------------------------------------

def builtin_search_dirs() -> list[Path]:
    """Directories searched out of the box, covering common agents."""
    home = Path.home()
    candidates = [
        home / ".codex" / "skills",               # OpenAI Codex
        home / ".agents" / "skills",              # Agents (OpenAI standard)
        home / ".claude" / "skills",              # Claude Code
        home / ".cursor" / "skills",              # Cursor
        home / ".codeium" / "windsurf" / "skills", # Windsurf
        home / ".config" / "opencode" / "skill",  # opencode
        home / ".cline" / "skills",               # Cline
        home / ".config" / "skills",              # XDG-style shared skills
    ]

    # Workspace-local skill directories
    for root in os.environ.get("WORKSPACE_ROOTS", "").split(os.pathsep):
        root = root.strip()
        if not root:
            continue
        p = Path(root)
        candidates.extend([
            p / ".codex" / "skills",
            p / ".agents" / "skills",
            p / ".claude" / "skills",
            p / "skills",
        ])

    # Environment-provided custom sources (uses os.pathsep)
    for extra in os.environ.get("SKILL_BRIDGE_SOURCES", "").split(os.pathsep):
        extra = extra.strip()
        if extra:
            candidates.append(Path(extra))

    return dedupe_paths(candidates)


def load_custom_sources() -> list[Path]:
    """Load user-registered sources from config file."""
    f = custom_sources_file()
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return [Path(p) for p in data.get("sources", [])]
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARNING: could not read {f}: {e}", file=sys.stderr)
        return []


def dedupe_paths(paths: list[Path]) -> list[Path]:
    """Remove duplicate/existing-resolved paths, preserve order."""
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        try:
            resolved = p.resolve()
        except (OSError, RuntimeError):
            resolved = p
        if resolved not in seen:
            seen.add(resolved)
            out.append(p)
    return out


def search_dirs() -> list[Path]:
    """All directories searched for skills."""
    return dedupe_paths(builtin_search_dirs() + load_custom_sources())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_valid_skill(path: Path) -> bool:
    return path.is_dir() and (path / "SKILL.md").exists()


def is_bridged_copy(target: Path) -> bool:
    """Check whether target is a copy/junction bridge we created (from manifest)."""
    manifest = load_copy_manifest()
    return target.name in manifest


def load_copy_manifest() -> dict:
    f = bridge_config_dir() / "copy-manifest.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_copy_manifest(data: dict) -> None:
    d = bridge_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / "copy-manifest.json"
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")


def show(path: Path) -> str:
    """Display path with ~ for home."""
    s = str(path)
    home = str(Path.home())
    if s.startswith(home):
        return "~" + s[len(home):]
    return s


def _unix_strategies(src: Path, target: Path) -> list[str]:
    """Link strategies on Unix, in preference order."""
    return ["symlink", "copy"]


def win_junction(src: Path, target: Path) -> bool:
    """Create a directory junction on Windows (no admin needed)."""
    if not HAS_CTYPES or not hasattr(ctypes, "windll"):
        return False
    try:
        os.makedirs(target, exist_ok=True)

        FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        OPEN_EXISTING = 3
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        handle = ctypes.windll.kernel32.CreateFileW(
            str(target),
            0x40000000,  # GENERIC_WRITE
            0,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            return False
        try:
            # Substitute name uses native NT device path prefix
            sub_wide = "\\??\\" + str(src)
            print_wide = str(src)
            sub_bytes = sub_wide.encode("utf-16-le") + b"\x00\x00"
            print_bytes = print_wide.encode("utf-16-le") + b"\x00\x00"

            mount_payload = struct.pack(
                "<HHHH",
                0,                       # SubstituteNameOffset
                len(sub_bytes),          # SubstituteNameLength
                len(sub_bytes),          # PrintNameOffset
                len(print_bytes),        # PrintNameLength
            ) + sub_bytes + print_bytes

            reparse_buf = struct.pack(
                "<IHH",
                0xA0000003,              # IO_REPARSE_TAG_MOUNT_POINT
                len(mount_payload),      # ReparseDataLength
                0,                       # Reserved
            ) + mount_payload

            bytes_returned = wintypes.DWORD()
            ok = ctypes.windll.kernel32.DeviceIoControl(
                handle,
                0x000900A4,  # FSCTL_SET_REPARSE_POINT
                reparse_buf,
                len(reparse_buf),
                None, 0,
                ctypes.byref(bytes_returned),
                None,
            )
            return bool(ok)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return False


def make_link(src: Path, target: Path, force_copy: bool) -> bool:
    """Create link or copy. Returns the mode used, or None on failure."""
    if force_copy:
        try:
            shutil.copytree(src, target)
            return "copy"
        except (OSError, shutil.Error) as e:
            print(f"ERROR: copy failed: {e}", file=sys.stderr)
            return None

    if IS_WINDOWS:
        try:
            os.symlink(src, target, target_is_directory=True)
            return "symlink"
        except (OSError, NotImplementedError):
            pass
        try:
            if win_junction(src, target):
                return "junction"
        except Exception:
            pass
        try:
            shutil.copytree(src, target)
            return "copy"
        except (OSError, shutil.Error) as e:
            print(f"ERROR: could not link or copy: {e}", file=sys.stderr)
            return None
    for strategy in _unix_strategies(src, target):
        try:
            if strategy == "symlink":
                os.symlink(src, target, target_is_directory=True)
            else:
                shutil.copytree(src, target)
            return "symlink" if strategy == "symlink" else "copy"
        except OSError:
            last = strategy
    print(f"ERROR: could not link or copy ({last}).", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def find_skill(name: str) -> list[Path]:
    results: list[Path] = []
    for base in search_dirs():
        if not base.exists():
            continue
        candidate = base / name
        if is_valid_skill(candidate):
            results.append(candidate)
    return results


def cmd_search(name: str) -> int:
    results = find_skill(name)
    if not results:
        print(f"No skill named '{name}' found.")
        print("Search locations:")
        for d in search_dirs():
            marker = " (custom)" if d in load_custom_sources() else ""
            print(f"  {show(d)}{marker}")
        return 1
    print(f"Found '{name}':")
    for r in results:
        target = codex_skills_dir() / name
        already = ""
        if target.is_symlink():
            try:
                already = " [BRIDGED]" if target.resolve() == r.resolve() else ""
            except OSError:
                pass
        print(f"  {show(r)}{already}")
    return 0


def cmd_link(src_str: str, force_copy: bool, force: bool) -> int:
    src = Path(src_str).expanduser().resolve()
    if not src.exists():
        # Try searching by name
        matches = find_skill(src_str)
        if len(matches) == 1:
            src = matches[0]
            print(f"Resolved '{src_str}' to {show(src)}")
        elif len(matches) > 1:
            print(f"Multiple matches for '{src_str}':")
            for m in matches:
                print(f"  {show(m)}")
            print("Please pass a full path.")
            return 1
        else:
            # Accept relative paths that aren't skills yet
            pass

    if not is_valid_skill(src):
        print(f"ERROR: not a valid skill (missing SKILL.md): {show(src)}")
        return 1

    target = codex_skills_dir() / src.name
    codex_skills_dir().mkdir(parents=True, exist_ok=True)

    if target.is_symlink():
        if not force:
            print(f"NOTE: '{target.name}' is already bridged. Use --force to replace.")
            return 1
        target.unlink()
    elif target.exists():
        # Real directory (or copy/junction) already there
        if force and is_bridged_copy(target):
            shutil.rmtree(target, ignore_errors=True)
        else:
            print(f"ERROR: '{target.name}' already exists. "
                  f"Use --force to overwrite a previous bridge, "
                  f"or remove it manually if it is a real skill.", file=sys.stderr)
            return 1

    mode = make_link(src, target, force_copy)
    if not mode:
        return 1

    # Record non-symlink bridges in manifest so unlink/list can identify them
    if mode in ("copy", "junction"):
        manifest = load_copy_manifest()
        manifest[target.name] = {
            "source": str(src),
            "type": mode,
        }
        save_copy_manifest(manifest)
    else:
        # Clear stale manifest entry when switching back to a pure symlink
        manifest = load_copy_manifest()
        if target.name in manifest:
            del manifest[target.name]
            save_copy_manifest(manifest)

    print(f"Bridged ({mode}): {src.name}")
    print(f"  source: {show(src)}")
    print(f"  target: {show(target)}")
    return 0


def cmd_unlink(name: str) -> int:
    target = codex_skills_dir() / name
    if target.is_symlink():
        target.unlink()
        print(f"Removed symlink: {name}")
        return 0

    manifest = load_copy_manifest()
    if name in manifest and target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
        del manifest[name]
        save_copy_manifest(manifest)
        print(f"Removed copy-bridge: {name}")
        return 0

    if target.is_dir():
        print(f"Refusing to remove real directory: {show(target)}", file=sys.stderr)
        return 1

    print(f"No bridged skill '{name}' found.")
    return 1


def cmd_list() -> int:
    base = codex_skills_dir()
    if not base.exists():
        print("No codex skills directory found.")
        return 0

    script_name = Path(__file__).resolve().parent.parent.name
    manifest = load_copy_manifest()
    bridged = []

    for item in sorted(base.iterdir()):
        if item.is_symlink():
            try:
                dest = item.resolve()
                bridged.append((item.name, dest, "symlink"))
            except OSError:
                bridged.append((item.name, None, "broken"))
        elif item.is_dir() and item.name in manifest and item.name != script_name:
            bridged.append((item.name, Path(manifest[item.name]["source"]), "copy"))

    if not bridged:
        print("No bridged skills currently.")
        return 0

    print("Bridged skills:")
    for name, dest, kind in bridged:
        if dest is None:
            print(f"  {name} -> [broken symlink]")
        else:
            print(f"  {name} -> {show(dest)}  [{kind}]")
    return 0


def cmd_sources(args: list[str]) -> int:
    f = custom_sources_file()
    d = bridge_config_dir()
    d.mkdir(parents=True, exist_ok=True)

    if not args or args[0] == "list":
        builtin = builtin_search_dirs()
        custom = load_custom_sources()
        print("Built-in search directories:")
        for b in builtin:
            print(f"  {show(b)}")
        print("\nCustom sources:")
        if custom:
            for c in custom:
                exists = "[ok]" if c.exists() else "[missing]"
                print(f"  {show(c)}  {exists}")
        else:
            print("  (none)")
        print(f"\nConfig file: {show(f)}")
        return 0

    sub = args[0]
    if sub == "add":
        if len(args) < 2:
            print("Usage: bridge.py sources add <path>")
            return 1
        p = Path(args[1]).expanduser().resolve()
        data = {"sources": []}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        sources = [Path(x) for x in data.get("sources", [])]
        if p in sources:
            print(f"Already registered: {show(p)}")
            return 0
        if not p.exists():
            print(f"NOTE: path does not exist (registered anyway): {show(p)}")
        sources.append(p)
        data["sources"] = [str(x) for x in sources]
        f.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Added source: {show(p)}")
        return 0

    if sub == "remove":
        if len(args) < 2:
            print("Usage: bridge.py sources remove <path>")
            return 1
        p = Path(args[1]).expanduser().resolve()
        if not f.exists():
            print("No custom sources registered.")
            return 1
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("Config file corrupted.")
            return 1
        sources = [Path(x) for x in data.get("sources", [])]
        if p not in sources:
            print(f"Not found: {show(p)}")
            return 1
        sources.remove(p)
        data["sources"] = [str(x) for x in sources]
        f.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Removed source: {show(p)}")
        return 0

    print(f"Unknown sources subcommand: {sub}")
    print("Usage: bridge.py sources [list|add <path>|remove <path>]")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    cmd = argv[1]
    args = argv[2:]
    flags = [a for a in args if a.startswith("-")]
    pos = [a for a in args if not a.startswith("-")]
    force_copy = any(f in ("-c", "--copy") for f in flags)
    force = any(f in ("-f", "--force") for f in flags)

    if cmd == "search":
        if not pos:
            print("Usage: bridge.py search <name>")
            return 1
        return cmd_search(pos[0])
    if cmd == "link":
        if not pos:
            print("Usage: bridge.py link <source-or-skill-name> [-c|--copy] [-f|--force]")
            return 1
        return cmd_link(pos[0], force_copy, force)
    if cmd == "unlink":
        if not pos:
            print("Usage: bridge.py unlink <name>")
            return 1
        return cmd_unlink(pos[0])
    if cmd == "list":
        return cmd_list()
    if cmd == "sources":
        return cmd_sources(pos)

    print(f"Unknown command: {cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
