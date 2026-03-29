from __future__ import annotations

from capabilities.skills.base_skill import BaseSkill


class SkillRegistry:
    """
    Global skill registry shared by all agents.
    """

    def __init__(self):
        self.skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        if skill.name in self.skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self.skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill:
        if name not in self.skills:
            raise ValueError(f"Skill '{name}' not found")
        return self.skills[name]

    def list_skills(self) -> list[str]:
        return list(self.skills.keys())

    def describe_skill(self, name: str) -> dict:
        return self.get(name).describe()

    def list_skill_descriptions(self) -> dict[str, dict]:
        return {
            name: skill.describe()
            for name, skill in self.skills.items()
        }

    def execute(self, *, skill_name: str, **kwargs):
        skill = self.get(skill_name)
        return skill.execute(**kwargs)
