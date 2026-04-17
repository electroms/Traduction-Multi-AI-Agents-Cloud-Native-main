# Dockerfile pour GitHub Copilot CLI dans un environnement conteneur sécurisé

FROM python:3.12.10-slim

# Arguments de build (
# COPILOT_VERSION pour choisir la version du SDK Copilot CLI,
# NODE_MAJOR pour la version majeure Node.js (20+ recommandé)
ARG COPILOT_VERSION=latest
ARG NODE_MAJOR=20

# Variables d'environnement
# - DEBIAN_FRONTEND=noninteractive empêche apt d'attendre des entrées utilisateur
# - PYTHONUNBUFFERED=1 désactive le buffering stdout/stderr pour logs en temps réel
# - PYTHONDONTWRITEBYTECODE=1 évite la création de fichiers pyc
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Note sur le token :
# Le jeton GitHub Copilot est passé via docker run -e GITHUB_COPILOT_TOKEN=xxx
# ou via un fichier d'environnement --env-file

# Installation des dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Installation de Node.js 20+ depuis NodeSource
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Vérifier l'installation de Node.js et npm
RUN node --version && npm --version

# Installation globale du Copilot CLI via npm
RUN npm install -g @github/copilot@${COPILOT_VERSION}

# Créer le répertoire de travail dans le conteneur
WORKDIR /work

# Copier requirements.txt en premier pour profiter du cache Docker
COPY requirements.txt /work/requirements.txt

# Installation des dépendances Python
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copier le code applicatif (main.py)
COPY main.py /work/main.py

# Métadonnées du conteneur pour identification
LABEL project="ghcli-blog-agent" \
      description="Démo GitHub Copilot CLI avec SDK Python pour agent de blog"

# Commande par défaut au démarrage du conteneur
CMD ["python", "main.py"]
