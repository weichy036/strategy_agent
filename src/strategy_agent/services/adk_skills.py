from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from google.adk.skills.models import Frontmatter, Resources, Script, Skill
from google.adk.tools.skill_toolset import SkillToolset

from strategy_agent.config import PROJECT_ROOT


def create_quant_backtest_skill_toolset() -> SkillToolset:
    return SkillToolset(skills=[load_local_skill(PROJECT_ROOT / "skills" / "quant_backtest_cn")])


def load_local_skill(skill_dir: Path) -> Skill:
    skill_md = skill_dir / "SKILL.md"
    frontmatter, instructions = _read_skill_markdown(skill_md)
    return Skill(
        frontmatter=Frontmatter.model_validate(frontmatter),
        instructions=instructions.strip(),
        resources=_read_resources(skill_dir),
    )


def _read_skill_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} 缺少 YAML frontmatter")

    _, raw_frontmatter, body = text.split("---", 2)
    parsed = yaml.safe_load(raw_frontmatter) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} frontmatter 必须是对象")
    return parsed, body


def _read_resources(skill_dir: Path) -> Resources:
    return Resources(
        references=_read_text_files(skill_dir / "references"),
        assets=_read_text_files(skill_dir / "assets"),
        scripts={path.name: Script(src=path.read_text(encoding="utf-8")) for path in sorted((skill_dir / "scripts").glob("*")) if path.is_file()},
    )


def _read_text_files(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


__all__ = ["create_quant_backtest_skill_toolset", "load_local_skill"]
