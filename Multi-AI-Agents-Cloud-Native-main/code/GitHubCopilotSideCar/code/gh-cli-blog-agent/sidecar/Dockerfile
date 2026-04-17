# Dockerfile pour le conteneur sidecar du Copilot CLI Blog Agent
# Ce fichier définit l'image nécessaire à l'exécution du micro-service de blog.

FROM python:3.12.10-slim

# Argument de build pour version Copilot CLI (par défaut : latest)
ARG COPILOT_VERSION=latest

# Variables d'environnement pour un build non interactif et un Python propre
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Installation des dépendances système de base
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    xz-utils \
    git \
    && rm -rf /var/lib/apt/lists/*

# Installation de Node.js 20.x via archive officielle (meilleure portabilité)
ARG NODE_VERSION=20.20.0
RUN DPKG_ARCH=$(dpkg --print-architecture) \
    && case "${DPKG_ARCH}" in amd64) ARCH=x64;; arm64) ARCH=arm64;; armhf) ARCH=armv7l;; *) ARCH=${DPKG_ARCH};; esac \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${ARCH}.tar.xz" -o node.tar.xz \
    && tar -xJf node.tar.xz -C /usr/local --strip-components=1 --no-same-owner \
    && rm -f node.tar.xz \
    && ln -sf /usr/local/bin/node /usr/local/bin/nodejs

# Validation des versions installées de Node.js et npm
RUN node --version && npm --version

# Installation globale de GitHub Copilot CLI
RUN npm install -g @github/copilot@${COPILOT_VERSION}

# Définition du dossier de travail pour le conteneur
WORKDIR /work

# Copier requirements.txt en premier pour optimiser le cache des couches Docker
COPY requirements.txt /work/requirements.txt

# Installation des dépendances Python depuis requirements
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copier le script principal de l'agent dans le conteneur
COPY main.py /work/main.py

# Étiquettes metadata pour identification d'image/services
LABEL project="ghcli-blog-agent" \
      description="GitHub Copilot CLI Blog Agent - Sidecar Container"

# Exposer le port 8001 utilisé par l'API de l'agent
EXPOSE 8001

# Commande par défaut au lancement du conteneur
CMD ["python", "main.py"]
