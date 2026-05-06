# Skills system (plugins)

Jarvis charge les skills automatiquement depuis :
- `services/orchestrator/app/skills/builtin/` (livrés avec le code)
- `/skills/` (volume monté pour tes propres plugins)

Hot-reload sans redémarrer l'orchestrator :

```bash
curl -X POST http://orchestrator:8001/skills/reload
# ou
curl https://jarvis.local/api/admin/skills/reload      # si proxifié plus tard
```

## Anatomie d'un skill

```python
# /skills/my_skill.py
from app.skills import Skill   # ou: from . import Skill si builtin


async def _hello(args: dict, ctx: dict) -> dict:
    name = args.get("name", "ami")
    return {"greeting": f"Bonjour {name}"}


def register(s: Skill) -> None:
    s.name = "hello"
    s.description = "Salutations personnalisées"
    s.tool(
        name="say_hello",
        description="Renvoie une salutation personnalisée",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
        },
        handler=_hello,
        requires_admin=False,
    )
```

Le tool est immédiatement disponible pour le LLM via tool calling. Le `ctx`
fourni au handler contient `session_id`, `user_id`, `is_owner`.

## Skills builtins

| Nom | Tools | Description |
|---|---|---|
| `time` | `time_now` | Heure et date courantes |
| `weather` | `weather_now` | Météo via Open-Meteo (sans clé) |
| `briefing` | `briefing_today` | Météo + agenda + alertes + IoT |
| `routines` | `routines_list/create/enable/run` | Gérer les scénarios |
| `presence` | `presence_set_away/status` | Mode absence + simulation présence |
| `explain` | `explain_last_action` | Trace du dernier raisonnement |

## Permissions

Si `requires_admin=True` sur un tool, l'orchestrator vérifie :
- voix-print ≥ seuil accept (sinon zone grise → challenge phrase)
- AASIST liveness humaine
- cooldown owner (1 commande / 30s)

Le tool est rejeté avec `"Cette action est réservée à mon créateur."` si la
voix n'est pas authentifiée.
