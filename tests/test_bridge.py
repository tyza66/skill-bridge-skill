#!/usr/bin/env python3
"""
Self-test for skill-bridge. Runs against an isolated CODEX_HOME and temp
directories so the user's real skills are never touched.

Usage: python3 tests/test_bridge.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "bridge.py"

passed = 0
failed = 0


def run(br_py: Path, *args: str, cwd: Path = None):
    return subprocess.run(
        [sys.executable, str(br_py), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")
        if detail:
            print(f"        {detail}")


def run_with(br_py: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(br_py), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def make_skill(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\n# {name}\n",
        encoding="utf-8",
    )
    return d


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="skill-bridge-test-") as tmp:
        tmp = Path(tmp)
        home = tmp / "home"
        (home / ".codex").mkdir(parents=True)
        src_dir = tmp / "sources"
        src_dir.mkdir()

        env = dict(os.environ)
        env["CODEX_HOME"] = str(home / ".codex")
        env["SKILL_BRIDGE_SOURCES"] = str(src_dir)


        print("\n[1] sources list")
        r = run_with(BRIDGE, env, "sources", "list")
        report("sources list runs", r.returncode == 0, r.stderr)

        print("\n[2] link by full path (symlink)")
        skill_a = make_skill(src_dir, "alpha")
        r = run_with(BRIDGE, env, "link", str(skill_a))
        target = home / ".codex" / "skills" / "alpha"
        report("symlink created", target.is_symlink())
        report("symlink resolves to source", target.resolve() == skill_a.resolve())

        print("\n[3] link by name")
        skill_b = make_skill(src_dir, "beta")
        r = run_with(BRIDGE, env, "link", "beta")
        tgt_b = home / ".codex" / "skills" / "beta"
        report("name-resolved symlink created", tgt_b.is_symlink())

        print("\n[4] link with --copy records manifest")
        skill_c = make_skill(src_dir, "gamma")
        r = run_with(BRIDGE, env, "link", str(skill_c), "--copy")
        tgt_c = home / ".codex" / "skills" / "gamma"
        report("copy is a real directory", tgt_c.is_dir() and not tgt_c.is_symlink())
        manifest = json.loads(
            (home / ".codex" / "skill-bridge" / "copy-manifest.json").read_text(encoding="utf-8")
        )
        report("manifest records copy", "gamma" in manifest)

        print("\n[5] list shows bridges")
        r = run_with(BRIDGE, env, "list")
        report("list mentions alpha", "alpha" in r.stdout)
        report("list mentions beta", "beta" in r.stdout)
        report("list mentions gamma", "gamma" in r.stdout)
        report("list marks copy mode", "[copy]" in r.stdout)

        print("\n[6] unlink")
        r = run_with(BRIDGE, env, "unlink", "alpha")
        report("symlink removed", not target.is_symlink() and not target.exists())
        r = run_with(BRIDGE, env, "unlink", "gamma")
        report("copy removed", not tgt_c.exists())
        manifest = json.loads(
            (home / ".codex" / "skill-bridge" / "copy-manifest.json").read_text(encoding="utf-8")
        )
        report("manifest cleared for gamma", "gamma" not in manifest)

        print("\n[7] refusing to delete a real (non-bridge) directory")
        real = home / ".codex" / "skills" / "real-thing"
        real.mkdir(parents=True)
        (real / "SKILL.md").write_text("---\nname: real-thing\n---\n", encoding="utf-8")
        r = run_with(BRIDGE, env, "unlink", "real-thing")
        report("unlink refuses for real dir", r.returncode != 0)
        report("real dir still present", real.is_dir())

        print("\n[8] refusing to overwrite a real dir without --force")
        skill_d = make_skill(src_dir, "real-thing")
        r = run_with(BRIDGE, env, "link", str(skill_d))
        report("link refuses for real dir", r.returncode != 0)

        print("\n[9] --force replaces a bridge")
        first = make_skill(src_dir, "delta")
        run_with(BRIDGE, env, "link", str(first))
        second = make_skill(tmp / "other", "delta")
        r = run_with(BRIDGE, env, "link", str(second), "--force")
        tgt_d = home / ".codex" / "skills" / "delta"
        report("force replaced symlink", tgt_d.resolve() == second.resolve())

        print("\n[10] sources add/remove")
        extra = tmp / "extra"
        extra.mkdir()
        r = run_with(BRIDGE, env, "sources", "add", str(extra))
        report("source added", r.returncode == 0)
        r = run_with(BRIDGE, env, "sources", "remove", str(extra))
        report("source removed", r.returncode == 0)

        print("\n[11] search finds skill")
        r = run_with(BRIDGE, env, "search", "alpha")
        report("search hits", "alpha" in r.stdout and r.returncode == 0)
        r = run_with(BRIDGE, env, "search", "nope-not-here")
        report("search misses cleanly", r.returncode != 0)

        print("\n[12] invalid skill rejected")
        bogus = tmp / "bogus"
        bogus.mkdir()
        r = run_with(BRIDGE, env, "link", str(bogus))
        report("missing SKILL.md rejected", r.returncode != 0)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    # Allow env override of the bridge script for test isolation
    bridge_env = os.environ.get("BRIDGE_PY")
    if bridge_env:
        BRIDGE = Path(bridge_env)
    sys.exit(main())
