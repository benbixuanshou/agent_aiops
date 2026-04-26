"""
Skill loader for .claude/skills/*/SKILL.md files.
Compatible with Claude Code's native skill format.
Three-level progressive disclosure:
  Level 1 — Metadata (name + description) always loaded
  Level 2 — SKILL.md body injected when matched
  Level 3 — references/* scripts/* loaded on demand
"""

from pathlib import Path

import yaml


class SkillLoader:
    def __init__(self, skill_dir: str = ".claude/skills"):
        self.skills: dict[str, dict] = {}
        self._descriptions: list[str] = []
        self._load_all(skill_dir)

    def _load_all(self, base_dir: str):
        base = Path(base_dir)
        if not base.exists():
            return
        for skill_dir in base.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            meta, body = self._parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            name = meta.get("name", skill_dir.name)

            self.skills[name] = {
                "name": name,
                "description": meta.get("description", ""),
                "allowed_tools": meta.get("allowed-tools", []),
                "body": body,
                "refs_dir": skill_dir / "references",
                "scripts_dir": skill_dir / "scripts",
            }
            self._descriptions.append(f"- {name}: {meta.get('description', '')}")

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return meta, body
        return {}, text

    def match(self, query: str, top_k: int = 2) -> list[dict]:
        """Match skills by keyword overlap with query."""
        query_lower = query.lower()
        scored = []
        for name, skill in self.skills.items():
            score = 0
            desc = skill["description"].lower()
            for word in query_lower.split():
                if word in desc or word in name.lower():
                    score += 1
            body = skill["body"].lower()
            for word in query_lower.split():
                if len(word) > 2 and word in body:
                    score += 2
            if score > 0:
                scored.append((score, name))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self.skills[name] for _, name in scored[:top_k]]

    def inject_skills(self, base_prompt: str, matched: list[dict]) -> str:
        if not matched:
            return base_prompt

        blocks = []
        for s in matched:
            blocks.append(
                f"<!-- SKILL: {s['name']} -->\n"
                f"## 技能指引: {s['name']}\n\n"
                f"{s['body']}"
            )
        return base_prompt + "\n\n---\n\n" + "\n\n---\n\n".join(blocks)
