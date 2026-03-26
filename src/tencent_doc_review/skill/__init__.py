"""Skill-layer request/response contracts shared by OpenClaw and Claude Code."""

from .skill_protocol import SkillRequest, SkillResponse, SkillRuntimeInfo

__all__ = [
    "SkillRequest",
    "SkillResponse",
    "SkillRuntimeInfo",
]
