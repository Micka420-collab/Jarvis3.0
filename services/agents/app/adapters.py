"""Adapters pour les agents externes (Hermes, OpenClaw, MCP, mock).

Chaque adapter implémente le protocole minimal :

  spawn(goal, context) → AsyncIterator[str]   # tokens / lignes en streaming
  finalize() → str                              # résumé du résultat

Les adapters ne sauvegardent pas l'état des tâches : c'est le rôle de
TaskRegistry. Ils exposent une simple boucle async qui yield des updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

log = logging.getLogger("agents.adapters")


@dataclass
class AgentInfo:
    name: str
    available: bool
    command: str
    notes: str = ""


class AgentAdapter(ABC):
    name: str = "abstract"

    @abstractmethod
    async def info(self) -> AgentInfo: ...

    @abstractmethod
    async def run(self, goal: str, context: dict) -> AsyncIterator[str]:
        """Lance la tâche et yield des chunks de sortie en streaming."""
        if False:  # pragma: no cover
            yield ""


# ---------------------------------------------------------------------------
# CLI generic adapter — spawn un binaire avec un prompt
# ---------------------------------------------------------------------------


class CLIAdapter(AgentAdapter):
    """Adapter générique : pipe le prompt sur stdin, capture stdout en streaming.

    Configuration (env vars ou explicit) :
        AGENT_<NAME>_CMD = "hermes" ou "openclaw chat -" etc.
        AGENT_<NAME>_TIMEOUT_S = 300
        AGENT_<NAME>_NOTES = "..."
    """

    def __init__(self, name: str, command: str, timeout_s: int = 300, notes: str = "") -> None:
        self.name = name
        self.command = command
        self.timeout_s = timeout_s
        self.notes = notes

    async def info(self) -> AgentInfo:
        # vérifie si le binaire est dans le PATH
        bin_name = shlex.split(self.command)[0]
        proc = await asyncio.create_subprocess_exec(
            "which", bin_name, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        out, _ = await proc.communicate()
        return AgentInfo(
            name=self.name,
            available=bool(out.strip()),
            command=self.command,
            notes=self.notes,
        )

    async def run(self, goal: str, context: dict) -> AsyncIterator[str]:
        """Lance la commande, pipe `goal` sur stdin, stream stdout ligne par ligne."""
        args = shlex.split(self.command)
        log.info("agent=%s spawn cmd=%s", self.name, args)
        env = {**os.environ}
        # passe le contexte utile en variable d'env
        for k, v in context.items():
            if isinstance(v, (str, int, float, bool)):
                env[f"JARVIS_{k.upper()}"] = str(v)
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        except FileNotFoundError as e:
            yield json.dumps({"type": "error", "message": f"binaire introuvable: {e}"})
            return

        # envoie le goal sur stdin et close
        if proc.stdin is not None:
            proc.stdin.write(goal.encode("utf-8") + b"\n")
            await proc.stdin.drain()
            proc.stdin.close()

        try:
            async with asyncio.timeout(self.timeout_s):
                if proc.stdout is None:
                    return
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    yield line.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            proc.kill()
            yield json.dumps({"type": "error", "message": f"timeout {self.timeout_s}s"})
        finally:
            await proc.wait()
            yield json.dumps({"type": "exit", "code": proc.returncode})


# ---------------------------------------------------------------------------
# MCP adapter — utilise le protocole MCP officiel
# ---------------------------------------------------------------------------


class MCPAdapter(AgentAdapter):
    """Adapter MCP : Jarvis devient client d'un MCP server fourni par l'agent.

    Hermes et OpenClaw exposent tous deux MCP. La config nécessite le chemin
    du binaire MCP et ses arguments.

    Note : pour les serveurs MCP qui nécessitent une session interactive,
    préférer CLIAdapter (plus simple).
    """

    def __init__(self, name: str, command: str, args: list[str] | None = None, notes: str = "") -> None:
        self.name = name
        self.command = command
        self.args = args or []
        self.notes = notes

    async def info(self) -> AgentInfo:
        proc = await asyncio.create_subprocess_exec(
            "which", self.command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        out, _ = await proc.communicate()
        return AgentInfo(
            name=self.name,
            available=bool(out.strip()),
            command=f"{self.command} {' '.join(self.args)}",
            notes=self.notes + " (MCP)",
        )

    async def run(self, goal: str, context: dict) -> AsyncIterator[str]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            yield json.dumps({"type": "error", "message": "lib `mcp` non installée"})
            return

        params = StdioServerParameters(command=self.command, args=self.args)
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    yield json.dumps({"type": "tools", "list": [t.name for t in tools]})
                    # Convention : on appelle un tool "agent_run" ou "execute_task" si présent.
                    # Sinon, on retourne juste la liste pour que le caller choisisse.
                    target = next(
                        (t for t in tools if t.name in {"agent_run", "execute_task", "run", "do"}),
                        None,
                    )
                    if target is None:
                        yield json.dumps(
                            {"type": "info", "message": "aucun tool 'run' générique trouvé"}
                        )
                        return
                    result = await session.call_tool(target.name, {"goal": goal, **context})
                    for c in result.content or []:
                        text = getattr(c, "text", None) or str(c)
                        yield text
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"MCP error: {e}"})


# ---------------------------------------------------------------------------
# Mock adapter — pour les tests offline
# ---------------------------------------------------------------------------


class MockAdapter(AgentAdapter):
    name = "mock"

    async def info(self) -> AgentInfo:
        return AgentInfo(name="mock", available=True, command="(in-process)", notes="dev/test")

    async def run(self, goal: str, context: dict) -> AsyncIterator[str]:
        yield f"[mock] reçu : {goal}\n"
        await asyncio.sleep(0.1)
        yield "[mock] travail simulé...\n"
        await asyncio.sleep(0.1)
        yield f"[mock] terminé. Tu m'avais demandé : {goal[:50]}\n"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_default_registry() -> dict[str, AgentAdapter]:
    """Configurer via env vars :
        AGENT_HERMES_CMD     (default: "hermes")
        AGENT_OPENCLAW_CMD   (default: "openclaw chat")
        AGENT_HERMES_MCP     (path bin MCP optionnel)
        AGENT_OPENCLAW_MCP   (path bin MCP optionnel)
    """
    out: dict[str, AgentAdapter] = {}

    hermes_cmd = os.getenv("AGENT_HERMES_CMD", "hermes").strip()
    if hermes_cmd:
        out["hermes"] = CLIAdapter(
            name="hermes",
            command=hermes_cmd,
            timeout_s=int(os.getenv("AGENT_HERMES_TIMEOUT_S", "600")),
            notes="Hermes Agent (Nous Research)",
        )

    openclaw_cmd = os.getenv("AGENT_OPENCLAW_CMD", "openclaw chat -").strip()
    if openclaw_cmd:
        out["openclaw"] = CLIAdapter(
            name="openclaw",
            command=openclaw_cmd,
            timeout_s=int(os.getenv("AGENT_OPENCLAW_TIMEOUT_S", "600")),
            notes="OpenClaw (Steinberger)",
        )

    # MCP optionnels
    hermes_mcp = os.getenv("AGENT_HERMES_MCP", "").strip()
    if hermes_mcp:
        out["hermes-mcp"] = MCPAdapter(
            name="hermes-mcp", command=hermes_mcp, args=["mcp"], notes="Hermes via MCP"
        )

    if os.getenv("AGENTS_ENABLE_MOCK", "true").lower() == "true":
        out["mock"] = MockAdapter()

    return out
