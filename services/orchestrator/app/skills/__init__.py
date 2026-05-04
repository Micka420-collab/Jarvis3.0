"""Système de skills (plugins) extensible.

Un skill est un module Python avec une fonction `register(skill: Skill)` qui :
- ajoute une description (intent + exemples)
- enregistre des tools (schéma + handler)
- optionnellement déclare un cron / event handler proactif

Les skills sont auto-découverts dans `services/orchestrator/app/skills/builtin/`
et `/skills/` (volume monté hot-reloadable).
"""

from .registry import Skill, SkillRegistry, registry

__all__ = ["Skill", "SkillRegistry", "registry"]
