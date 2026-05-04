"""Registry central des skills.

API skill côté developer :

    # services/orchestrator/app/skills/builtin/weather.py
    from . import Skill
    def register(s: Skill) -> None:
        s.name = "weather"
        s.description = "Météo et prévisions"
        s.tool(
            name="weather_now",
            description="Météo actuelle d'une ville",
            input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
            handler=weather_handler,
        )
        s.cron(
            schedule="0 7 * * *",          # tous les jours à 7h
            handler=morning_briefing_cb,
        )
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("orchestrator.skills")

ToolHandler = Callable[[dict, dict], Awaitable[Any]]
# (arguments_du_LLM, contexte: {session_id, user_id, is_owner, role})
EventHandler = Callable[[dict], Awaitable[None]]


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    handler: ToolHandler
    requires_admin: bool = False


@dataclass
class CronDef:
    schedule: str  # spec cron simple : "M H DOM MON DOW"
    handler: EventHandler
    name: str = ""


@dataclass
class Skill:
    name: str = ""
    description: str = ""
    tools: list[ToolDef] = field(default_factory=list)
    crons: list[CronDef] = field(default_factory=list)
    event_handlers: dict[str, EventHandler] = field(default_factory=dict)

    def tool(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: ToolHandler,
        requires_admin: bool = False,
    ) -> None:
        self.tools.append(ToolDef(name, description, input_schema, handler, requires_admin))

    def cron(self, schedule: str, handler: EventHandler, name: str = "") -> None:
        self.crons.append(CronDef(schedule, handler, name or schedule))

    def on_event(self, stream: str, handler: EventHandler) -> None:
        self.event_handlers[stream] = handler


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def load_builtin(self) -> None:
        builtin_dir = Path(__file__).parent / "builtin"
        if not builtin_dir.is_dir():
            return
        for path in sorted(builtin_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_path(path, prefix="app.skills.builtin")

    def load_external(self, dir_path: str) -> None:
        """Charge les skills déposés en /skills (volume monté)."""
        d = Path(dir_path)
        if not d.is_dir():
            return
        for path in sorted(d.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_external_file(path)

    def _load_path(self, path: Path, prefix: str) -> None:
        mod_name = f"{prefix}.{path.stem}"
        try:
            module = importlib.import_module(mod_name)
            self._register_module(module, path.stem)
        except Exception as e:
            log.exception("skill %s import failed: %s", path.stem, e)

    def _load_external_file(self, path: Path) -> None:
        spec = importlib.util.spec_from_file_location(f"jarvis_skill_{path.stem}", path)
        if spec is None or spec.loader is None:
            return
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            self._register_module(module, path.stem)
        except Exception as e:
            log.exception("skill external %s failed: %s", path.stem, e)

    def _register_module(self, module: Any, default_name: str) -> None:
        if not hasattr(module, "register"):
            log.warning("skill %s sans register() — ignoré", default_name)
            return
        skill = Skill(name=default_name)
        module.register(skill)
        if not skill.name:
            skill.name = default_name
        self._skills[skill.name] = skill
        log.info(
            "skill chargé: %s (%d tools, %d crons, %d events)",
            skill.name,
            len(skill.tools),
            len(skill.crons),
            len(skill.event_handlers),
        )

    def all_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def all_tools(self) -> list[ToolDef]:
        out: list[ToolDef] = []
        for s in self._skills.values():
            out.extend(s.tools)
        return out

    def find_tool(self, name: str) -> ToolDef | None:
        for s in self._skills.values():
            for t in s.tools:
                if t.name == name:
                    return t
        return None

    def reload(self) -> None:
        """Hot-reload : ré-importe tous les skills builtins (signal SIGHUP)."""
        self._skills.clear()
        # purge sys.modules pour forcer ré-import
        for k in list(sys.modules):
            if k.startswith("app.skills.builtin.") or k.startswith("jarvis_skill_"):
                del sys.modules[k]
        self.load_builtin()
        self.load_external("/skills")
        log.info("skills hot-reload : %d skills actifs", len(self._skills))


registry = SkillRegistry()
