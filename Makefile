.PHONY: help up up-vision up-gpu down restart logs ps build pull clean test e2e e2e-phase1 fmt lint download-models enroll-voice enroll-face discover-ha

COMPOSE := docker compose

help:
	@echo "Jarvis 3.0 — commandes disponibles :"
	@echo "  make up              Démarre tous les services"
	@echo "  make up-gpu          Démarre avec override CUDA"
	@echo "  make down            Stoppe tous les services"
	@echo "  make restart         Redémarre tous les services"
	@echo "  make logs            Suit les logs (tous services)"
	@echo "  make logs s=gateway  Suit les logs d'un service précis"
	@echo "  make ps              Liste les conteneurs"
	@echo "  make build           Reconstruit les images locales"
	@echo "  make pull            Pull les images upstream"
	@echo "  make download-models Télécharge Whisper/Piper/ECAPA"
	@echo "  make enroll-voice    Lance l'enrôlement voix-print"
	@echo "  make enroll-face name=mickael image=./photo.jpg  Enrôle un visage"
	@echo "  make discover-ha     Synchronise les entités Home Assistant en BDD"
	@echo "  make up-vision       Démarre + service Frigate (profile vision)"
	@echo "  make test            Lance les tests unitaires"
	@echo "  make e2e             Lance les tests end-to-end"
	@echo "  make e2e-phase1      Test E2E voix bidir"
	@echo "  make clean           Supprime conteneurs + volumes"

up:
	$(COMPOSE) up -d

up-gpu:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
ifdef s
	$(COMPOSE) logs -f $(s)
else
	$(COMPOSE) logs -f
endif

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

pull:
	$(COMPOSE) pull

download-models:
	bash scripts/download_models.sh

enroll-voice:
	$(COMPOSE) exec voice python /app/scripts/enroll_voiceprint.py --user $(OWNER_USERNAME) --owner

enroll-face:
ifndef name
	$(error "name=<nom> requis (ex: make enroll-face name=mickael image=./photo.jpg)")
endif
ifdef image
	$(COMPOSE) exec vision python /app/scripts/enroll_face.py --name $(name) --image $(image)
else
	$(COMPOSE) exec vision python /app/scripts/enroll_face.py --name $(name) --camera 0
endif

discover-ha:
	$(COMPOSE) exec iot curl -fsS -X POST http://localhost:8002/discover/ha

up-vision:
	$(COMPOSE) --profile vision up -d

test:
	$(COMPOSE) exec gateway pytest /app/tests/unit -v

e2e:
	$(COMPOSE) exec gateway pytest /app/tests/e2e -v

e2e-phase1:
	$(COMPOSE) exec gateway pytest /app/tests/e2e/test_phase1_voice.py -v

fmt:
	$(COMPOSE) exec gateway ruff format /app
	cd frontend && npm run format

lint:
	$(COMPOSE) exec gateway ruff check /app
	cd frontend && npm run lint

clean:
	$(COMPOSE) down -v
	rm -rf volumes/ data/
