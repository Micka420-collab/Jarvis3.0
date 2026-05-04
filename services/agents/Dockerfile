# Image qui contient le service `agents` + Hermes + OpenClaw préinstallés.
# Le build est volontairement gros (~1 Go) car les agents sont des écosystèmes
# complets. Tu peux désactiver l'install si tu veux les piloter depuis l'host
# (cf. docs/agents.md, mode "host-side").

FROM python:3.12-slim

WORKDIR /app

# Toolchain pour les agents (npm, git, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ca-certificates build-essential \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# --- Hermes (Nous Research) — install optionnel via build arg ---
ARG INSTALL_HERMES=false
RUN if [ "$INSTALL_HERMES" = "true" ]; then \
      curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh -o /tmp/hermes.sh && \
      bash /tmp/hermes.sh && rm /tmp/hermes.sh ; \
    fi

# --- OpenClaw — install optionnel via build arg ---
ARG INSTALL_OPENCLAW=false
RUN if [ "$INSTALL_OPENCLAW" = "true" ]; then \
      curl -fsSL https://openclaw.ai/install.sh -o /tmp/oc.sh && \
      bash /tmp/oc.sh && rm /tmp/oc.sh ; \
    fi

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

EXPOSE 8005

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005", "--reload"]
