# skill-bridge

Temporarily use a skill from another agent directory without installing it permanently.

## Problem

You have a skill installed in one agent's directory (e.g. `~/.claude/skills/playwright`) but you're working in a different session that doesn't see it. Copying it over manually is tedious, and you don't want to permanently install it everywhere.

## Solution

`skill-bridge` links external skills into your current Codex skills directory. The skill becomes available instantly, can be removed cleanly when done, and the original is never modified.

## Platform Support

| OS | Link strategy |
|----|---------------|
| Linux / macOS | symlink (falls back to copy if the filesystem forbids it) |
| Windows | symlink (Win10+ Developer Mode) -> directory junction -> copy |

On Windows the junction fallback needs no administrator or Developer Mode, so the common case still avoids duplicating files.

## Agent Support

Skills are discovered across these directories by default:

- `~/.codex/skills`, `~/.agents/skills`
- `~/.claude/skills`
- `~/.cursor/skills`
- `~/.codeium/windsurf/skills`
- `~/.config/opencode/skill`
- `~/.cline/skills`
- `~/.config/skills`
- workspace-local `.codex/skills`, `.agents/skills`, `.claude/skills`, `skills` (from `WORKSPACE_ROOTS`)

Extra sources can be registered, and `SKILL_BRIDGE_SOURCES` supports ad-hoc search paths.

## Installation

Clone this skill into your Codex skills directory:

```bash
git clone https://github.com/tyza66/skill-bridge-skill ~/.codex/skills/skill-bridge
```

## Usage

Let `$B` be the script:

```bash
B="~/.codex/skills/skill-bridge/scripts/bridge.py"
```

### Search for a skill

```bash
python3 $B search <skill-name>
```

### Bridge a skill into the current session

```bash
# By name (auto-resolves when unique across search directories)
python3 $B link playwright

# By explicit path
python3 $B link /path/to/skills/playwright

# Force a physical copy instead of a link
python3 $B link playwright --copy

# Replace an existing bridge
python3 $B link playwright --force
```

### List bridged skills

```bash
python3 $B list
```

### Remove a bridge

```bash
python3 $B unlink playwright
```

Removes only the bridge we created. The original skill stays untouched.

### Manage custom search directories

```bash
python3 $B sources list
python3 $B sources add /path/to/skills
python3 $B sources remove /path/to/skills
```

Custom sources persist in `~/.codex/skill-bridge/sources.json`. For ad-hoc paths, set `SKILL_BRIDGE_SOURCES` (path-separated with `:` on Unix, `;` on Windows).

## Design Notes

- **Symlinks, junctions, or copies.** Links keep the skill in sync with its source; copies are the last resort and are tracked in a manifest so bridges can still be removed cleanly.
- **Non-destructive by default.** A real skill already occupying the target name is never overwritten; removing a bridge only removes bridges this tool created.
- **Manifest-based bookkeeping.** Junction and copy bridges are recorded in `~/.codex/skill-bridge/copy-manifest.json`, because unlike symlinks they cannot be detected by path inspection alone.

## Structure

```
skill-bridge/
├── SKILL.md              # Skill instructions and workflow
├── agents/openai.yaml    # UI metadata
├── scripts/bridge.py     # Core script (search / link / unlink / list / sources)
├── tests/test_bridge.py  # Self-test for the bridge workflow
└── README.md
```
