# skill-bridge

Temporarily use a skill from another agent directory without installing it permanently.

## Problem

You have a skill installed in one agent directory (e.g. `~/.agents/skills/playwright`) but you're working in a different session that doesn't see it. Copying it over manually is tedious, and you don't want to permanently install it everywhere.

## Solution

`skill-bridge` creates symlinks from external skill directories into your current Codex skills directory. The skill becomes available instantly, stays in sync with its source, and can be removed cleanly when done.

## Installation

Copy this skill into your Codex skills directory, or clone it:

```bash
git clone https://github.com/tyza66/skill-bridge-skill ~/.codex/skills/skill-bridge
```

## Usage

### Search for a skill

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py search <skill-name>
```

Searches `~/.codex/skills`, `~/.agents/skills`, and workspace-local skill directories.

### Bridge a skill into current session

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py link <source-path>
```

Creates a symlink in `~/.codex/skills/<skill-name>` pointing to the source. The skill is now discoverable by Codex.

### List bridged skills

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py list
```

### Remove a bridge

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py unlink <skill-name>
```

Removes only the symlink — the original skill is untouched.

## Design

- **Symlinks, not copies** — no duplication, always up-to-date with source
- **Cross-volume fallback** — automatically copies if symlinks aren't supported between volumes
- **Safe cleanup** — `unlink` only removes symlinks, never deletes real directories
- **Non-destructive** — refuses to overwrite existing real directories

## Structure

```
skill-bridge/
├── SKILL.md              # Skill instructions and workflow
├── agents/openai.yaml    # UI metadata
├── scripts/bridge.py     # Core script (search / link / unlink / list)
└── README.md
```
