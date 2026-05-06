"""Mode agent autonome : Jarvis enchaîne plusieurs tool calls pour atteindre
un objectif complexe en plusieurs étapes.

Différence avec le tool calling normal :
- Le LLM peut appeler **N tools en série** (par défaut 8 max)
- Chaque résultat est ré-injecté en contexte avant le tour suivant
- Le LLM décide explicitement quand il a terminé en émettant un message texte
  sans tool call (ou en appelant un tool spécial `agent_finalize`)
- Trace détaillée pour le bouton "Pourquoi ?" : on persiste chaque étape

Activé quand l'utilisateur dit explicitement « fais X, Y, Z », « organise-moi
mes mails et ma journée et lance la routine soir », etc. Heuristique simple :
si la requête contient ≥ 3 verbes d'action ou des conjonctions multiples, ou
si un meta-tool `enter_agent_mode` est appelé.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger("orchestrator.autonomous")

MAX_STEPS = 8


async def run_autonomous(
    initial_messages: list[dict],
    call_llm: Callable[[list[dict]], Awaitable[dict]],
    dispatch_tool: Callable[[str, dict, dict], Awaitable[Any]],
    gate_admin: Callable[[str, str], tuple[bool, str | None]],
    ctx: dict,
    max_steps: int = MAX_STEPS,
) -> dict:
    """Boucle d'agent : appelle le LLM, exécute les tools, récolte les résultats,
    rebouclte. S'arrête quand le LLM ne demande plus de tool ou que `max_steps`
    est atteint.

    Retourne :
      {
        "reply": str,
        "steps": [{"step": int, "tool": str, "args": dict, "result": Any}, ...],
        "halt_reason": "completed" | "max_steps" | "denied" | "error",
      }
    """
    history = list(initial_messages)
    steps: list[dict] = []
    final_text = ""

    for step_i in range(max_steps):
        try:
            out = await call_llm(history)
        except Exception as e:
            log.exception("LLM call failed at step %d: %s", step_i, e)
            return {
                "reply": "Désolé, le raisonnement a échoué.",
                "steps": steps,
                "halt_reason": "error",
            }

        text = out.get("text", "")
        tool_calls = out.get("tool_calls", [])
        if text:
            final_text = text

        if not tool_calls:
            history.append({"role": "assistant", "content": final_text})
            return {"reply": final_text, "steps": steps, "halt_reason": "completed"}

        history.append({"role": "assistant", "content": final_text, "tool_calls": tool_calls})

        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("input") if isinstance(tc.get("input"), dict) else {}

            allowed, challenge = gate_admin(ctx.get("session_id", ""), name)
            if not allowed:
                msg = f"Action '{name}' refusée — voix non autorisée."
                if challenge:
                    msg = f"J'ai besoin de te confirmer avec : {challenge}"
                steps.append({"step": step_i, "tool": name, "args": args, "result": {"error": "denied"}})
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "name": name,
                        "content": msg,
                    }
                )
                return {"reply": msg, "steps": steps, "halt_reason": "denied"}

            try:
                result = await dispatch_tool(name, args, ctx)
            except Exception as e:
                result = {"error": str(e)}
            steps.append({"step": step_i, "tool": name, "args": args, "result": result})
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": name,
                    "content": str(result),
                }
            )

    return {"reply": final_text or "J'ai épuisé mon budget d'étapes.", "steps": steps, "halt_reason": "max_steps"}


def is_autonomous_request(text: str) -> bool:
    """Heuristique : décide si une requête mérite le mode agent autonome.

    Critères :
    - 3+ conjonctions ou marqueurs séquentiels (« puis », « ensuite », « et »)
    - Verbes d'action multiples
    - Mots-clés : « organise », « gère », « prépare », « planifie »,
      « occupe-toi », « optimise »
    """
    t = text.lower()
    keywords = [
        "organise", "gère", "gere", "prépare", "prepare",
        "planifie", "occupe-toi", "optimise", "fais le tour",
        "passe en revue", "fais tout",
    ]
    if any(k in t for k in keywords):
        return True
    seq_markers = sum(t.count(m) for m in [" puis ", " ensuite ", " puis,", " ensuite,", " et "])
    return seq_markers >= 3
