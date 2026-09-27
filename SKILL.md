---
name: skill-bridge
description: Temporarily bridge a skill from another agent directory into the current session. Use when the user wants to use a skill that is installed elsewhere (another ~/.codex/skills, ~/.agents/skills, ~/.claude/skills, ~/.cursor/skills, ~/.codeium/windsurf/skills, or a custom directory) without permanently installing it.
---

# Skill Bridge

Bridge skills installed in other agent directories into the current session temporarily.

## When to Use

- The user mentions a skill by name that isn't in the current skill list but exists elsewhere on the machine
- The user wants to "borrow" or "try out" a skill from another project/agent (Codex, Claude Code, Cursor, Windsurf, Cline, opencode, etc.)
- The user says "use skill X from Y" where Y is a directory or agent name

## Environment

- **OS:** Linux, macOS, Windows
- **Link strategy:** symlink -> Windows junction -> copy (automatic fallback)
- **Search:** built-in agent directories, custom sources, `SKILL_BRIDGE_SOURCES` env var

## Workflow

### 1. Search for the skill

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py search <skill-name>
```

Built-in search directories:

- `~/.codex/skills` (Codex)
- `~/.agents/skills` (Agents standard)
- `~/.claude/skills` (Claude Code)
- `~/.cursor/skills` (Cursor)
- `~/.codeium/windsurf/skills` (Windsurf)
- `~/.config/opencode/skill` (opencode)
- `~/.cline/skills` (Cline)
- `~/.config/skills` (XDG-style)
- any `.codex/skills` / `.agents/skills` / `.claude/skills` / `skills` in `WORKSPACE_ROOTS`

### 2. Bridge (link or copy) the skill

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py link <source-path-or-skill-name> [--copy] [--force]
```

- `link <skill-name>` resolves the name automatically if it is unique across search directories
- `--copy` forces a physical copy instead of a link (useful for sandboxes that reject links, or Windows without symlink privileges)
- `--force` replaces an existing bridge

Default behavior: symlink; on Windows falls back to junction (no admin needed), then to copy. Cross-volume mounts that cannot symlink also fall back to copy.

### 3. Inform the user

Tell the user the skill is now available. They can reference it by name in subsequent requests.

### 4. Cleanup

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py unlink <skill-name>
```

Removes the link or the copy we registered. The original skill is never touched.

### Manage custom sources

```bash
# List built-in + custom search directories
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py sources list

# Register an extra skill directory to search
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py sources add /path/to/skills

# Unregister
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py sources remove /path/to/skills
```

Custom sources persist in `~/.codex/skill-bridge/sources.json`. For one-off use, set `SKILL_BRIDGE_SOURCES=/path/a:/path/b` (path-separated, `;` on Windows).

### List bridged skills

```bash
python3 ~/.codex/skills/skill-bridge/scripts/bridge.py list
```

Shows every bridged skill with its link mode (symlink, junction, or copy) and source.

## Safety

- Never modify or delete the original skill
- `unlink` removes only bridges we created; real directories are refused
- Copy/junction bridges are recorded in `~/.codex/skill-bridge/copy-manifest.json` so `unlink` and `list` can identify them even though they are not symlinks
- The manifest is updated whenever the bridge mode changes
