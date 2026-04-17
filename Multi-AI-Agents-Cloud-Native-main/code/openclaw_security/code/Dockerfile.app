# Dockerfile.app — image pour génération de podcast entièrement automatisée
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*  # nettoyage des caches d'apt après l'installation

RUN pip install --no-cache-dir \
    requests \
    serpapi \
    beautifulsoup4 \
    lxml  # dépendances Python pour la recherche web, le scraping et l'appel API

COPY auto_run.py podcast_generator.py deepsearch.py trend_scout.py ./

RUN mkdir -p /app/output  # dossier de sortie pour les scripts de podcast générés

# Entrypoint intelligent : SCHEDULE_HOURS=0 → exécution unique ; >0 → mode planifié
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["if [ \"${SCHEDULE_HOURS:-0}\" -gt 0 ]; then \
       python auto_run.py --schedule ${SCHEDULE_HOURS} --count ${TOPICS_PER_RUN:-1}; \
     else \
       python auto_run.py --count ${TOPICS_PER_RUN:-1}; \
     fi"]
