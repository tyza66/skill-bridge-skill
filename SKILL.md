---
name: skill-bridge
description: Temporarily bridge a skill from another agent directory into the current session. Use when the user wants to use a skill that is installed elsewhere (another ~/.codex/skills, ~/.agents/skills, or a project-local skills folder) without permanently installing it.
---

# Skill Bridge

Bridge skills installed in other agent directories into the current session temporarily.

## When to Use

- The user mentions a skill by name that isn't in the current skill list but exists elsewhere on the machine
- The user wants to "borrow" or "try out" a skill from another project/agent
- The user says "use skill X from Y" where Y is a directory or agent name

## Workflow

### 1. Search for the skill

Use `scripts/bridge.py search <name>` to find the skill across known directories:

```bash
python3 /path/to/skill-bridge/scripts/bridge.py search <skill-name>
```

This searches:
- `~/.codex/skills` (primary Codex skills)
- `~/.agents/skills` (Agents skills)
- Any `.codex/skills` or `.agents/skills` in workspace roots

### 2. Bridge (link) the skill

Once found, create a symlink so it becomes available:

```bash
python3 /path/to/skill-bridge/scripts/bridge.py link <source-path>
```

This creates a symlink from the source into `~/.codex/skills/<skill-name>`, making it discoverable by Codex.

### 3. Inform the user

Tell the user the skill is now available. They can reference it by name in subsequent requests.

### 4. Cleanup (optional)

When the user is done with the bridged skill:

```bash
python3 /path/to/skill-bridge/scripts/bridge.py unlink <skill-name>
```

This removes the symlink only — the original skill is untouched.

### List currently bridged skills

```bash
python3 /path/to/skill-bridge/scripts/bridge.py list
```

Shows all symlinked skills in `~/.codex/skills` that point to external locations.

## Notes

- Symlinks are preferred over copies — no duplication, and the skill stays up-to-date with its source
- If the target is on a different volume (may not support symlinks), fall back to copying
- Never modify the original skill — this is a read-only bridge
- If the skill name already exists in the target, warn the user before overwriting
