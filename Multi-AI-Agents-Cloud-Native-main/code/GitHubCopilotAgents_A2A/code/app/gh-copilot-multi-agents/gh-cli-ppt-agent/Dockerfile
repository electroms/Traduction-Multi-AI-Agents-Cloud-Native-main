# Dockerfile pour GitHub Copilot CLI dans un bac à sable sécurisé

FROM python:3.12.10-slim

# Arguments de construction
ARG COPILOT_VERSION=latest
ARG NODE_MAJOR=20

# Variables d'environnement
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Jeton GitHub Copilot - fournir via docker run -e GITHUB_COPILOT_TOKEN=xxx
# ou utiliser --env-file

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Installation de Node.js 20+
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Vérification de l'installation de Node.js et npm
RUN node --version && npm --version

# Installation globale de GitHub Copilot CLI via npm
RUN npm install -g @github/copilot@${COPILOT_VERSION}

# Création du répertoire de travail
WORKDIR /work

# Copie du fichier requirements.txt en premier pour meilleur cache des couches
COPY requirements.txt /work/requirements.txt

# Installation des dépendances Python
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copie des fichiers de l'application
COPY main.py /work/main.py

# Copie des compétences Copilot
COPY .copilot_skills /work/.copilot_skills

# Création du dossier de sorties PPT
RUN mkdir -p /work/ppt

# Ajout de labels pour l'identification et la documentation
LABEL project="ghcli-ppt-agent" \
      description="GitHub Copilot CLI Demo with Python SDK For PPT Agent"

# Commande par défaut pour lancer le script principal
CMD ["python", "main.py"]
