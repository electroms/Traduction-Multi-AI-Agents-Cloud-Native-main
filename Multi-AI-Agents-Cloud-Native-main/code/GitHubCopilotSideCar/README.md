# Agent de Blog - Modèle Dual-Sidecar Kubernetes

Basé sur l'architecture `prototype/sidecar`, déploie l'Agent de Blog GitHub Copilot avec un modèle **dual-sidecar** K8s.
- **Sidecar 1 (copilot-agent)** : Utilise le SDK GitHub Copilot pour générer du contenu
- **Sidecar 2 (skill-server)** : Service de gestion des compétences, sert SKILL.md
- **Main (blog-app)** : Visionneuse web Nginx pour les résultats

## Architecture

```
┌──────────────────── Pod: blog-agent ────────────────────────┐
│                                                              │
│  ┌─────────────────┐ ┌──────────────────┐ ┌──────────────┐  │
│  │  blog-app        │ │  copilot-agent   │ │  skill-server│  │
│  │  (Main)          │ │  (Sidecar 1)     │ │  (Sidecar 2) │  │
│  │                  │ │                  │ │              │  │
│  │  Nginx + Monitor │ │  FastAPI +       │ │  FastAPI     │  │
│  │                  │ │  Copilot SDK +   │ │  Skill API   │  │
│  │  Port: 80        │ │  Node.js         │ │              │  │
│  │                  │ │  Port: 8001      │ │  Port: 8002  │  │
│  │                  │ │                  │ │              │  │
│  │  read /blog/ ←───┼─┤ write blog/      │ │ sync skill/  │  │
│  │                  │ │ read skill/ ←────┼─┤              │  │
│  └────────┬─────────┘ └──────┬───┬───────┘ └──────┬───────┘  │
│           │                  │   │                │          │
│           └── blog-data ─────┘   └─ skills-shared ┘          │
│              (emptyDir)            (emptyDir)                │
│                                                              │
│  ConfigMap: blog-agent-skill (SKILL.md) → skill-server       │
│  Secret: blog-agent-secret (COPILOT_GITHUB_TOKEN)            │
└──────────────────────────────────────────────────────────────┘
```

**Responsabilités des Conteneurs :**
- **blog-app (Conteneur Principal)** : Serveur Nginx, affiche le contenu du blog généré par les sidecars, proxy inverse vers l'API Copilot Agent et l'API Skill, surveille le statut du répertoire blog
- **copilot-agent (Sidecar 1)** : Exécute l'application FastAPI, intègre le SDK GitHub Copilot + Node.js, lit les fichiers de compétences synchronisés par skill-server, génère des fichiers de blog et écrit dans le volume partagé
- **skill-server (Sidecar 2)** : Exécute l'application FastAPI, gère les fichiers SKILL.md, lit les définitions de compétences depuis ConfigMap et synchronise vers le volume partagé, fournit l'API de requête de compétences

**Flux de Données :** ConfigMap → Skill Server synchronise les fichiers de compétences → Copilot Agent lit les compétences et génère le blog → écrit dans le volume partagé → Le conteneur principal de l'app lit et sert

## Structure des Répertoires

```
gh-cli-blog-agent/
├── Makefile                 # Automatisation de construction/déploiement en un clic
├── README.md
├── app/                     # Conteneur principal (Blog App - Visionneuse Web Nginx)
│   ├── Dockerfile
│   ├── index.html           # Page d'accueil de la visionneuse de blog
│   ├── monitor.sh           # Script de surveillance du répertoire blog
│   └── nginx.conf           # Configuration Nginx (proxy inverse vers les deux sidecars)
├── sidecar/                 # Sidecar 1 (Copilot Agent - SDK GitHub Copilot)
│   ├── Dockerfile
│   ├── main.py              # Agent de Blog (FastAPI + SDK Copilot)
│   └── requirements.txt
├── skill-sidecar/           # Sidecar 2 (Serveur de Compétences - Gestion des Compétences)
│   ├── Dockerfile
│   ├── main.py              # Serveur de Compétences (FastAPI + Synchronisation des Compétences)
│   └── requirements.txt
└── k8s/                     # Manifestes Kubernetes
    ├── configmap.yaml       # Compétence de Blog (SKILL.md)
    ├── deployment.yaml      # Définition du Pod (principal + 2 sidecars)
    ├── secret.yaml          # Jeton GitHub Copilot
    └── service.yaml         # Service NodePort
```

## Prérequis

- Docker Desktop (macOS/Windows) ou Docker Engine (Linux)
- kubectl
- kind
- Jeton GitHub Copilot

> Le Makefile détecte automatiquement l'architecture de l'hôte : `x86_64 → linux/amd64`, `arm64/aarch64 → linux/arm64`.

### macOS

```bash
brew install kubectl kind
```

Ou via Makefile :

```bash
make install-tools-macos
```

### Linux

Assurez-vous que Docker Engine est installé et en cours d'exécution.

```bash
make install-tools-linux
```

> Les binaires sont installés dans `/usr/local/bin` et nécessitent `sudo`.

## Démarrage Rapide

### 1. Définir le Jeton

Modifiez `k8s/secret.yaml` et remplacez `YOUR_COPILOT_GITHUB_TOKEN_HERE` par votre jeton réel.

Ou utilisez la ligne de commande :

```bash
make set-token
```

### 2. Déploiement en Un Clic

```bash
make up
```

> `make up` effectuera automatiquement : vérification des dépendances → création du cluster kind → construction des images → chargement des images → déploiement des ressources K8s

### 3. Vérifier

```bash
# Vérifier le statut
make status

# Vérification de l'environnement
make doctor

# Test de fumée
make smoke
```

### 4. Accéder

```bash
make port-forward
```

Accédez aux URL suivantes :

| URL | Description |
|------|------|
| `http://localhost:8080/` | Page d'accueil de la visionneuse de blog (App Principale) |
| `http://localhost:8080/blog/` | Parcourir les fichiers de blog générés |
| `http://localhost:8080/agent/` | API Copilot Agent (proxy inverse vers Sidecar 1) |
| `http://localhost:8080/agent/health` | Vérification de santé de l'agent Copilot |
| `http://localhost:8080/skill/` | API Serveur de Compétences (proxy inverse vers Sidecar 2) |
| `http://localhost:8080/skill/skills` | Voir la liste des compétences disponibles |
| `http://localhost:8001/` | API Copilot Agent (accès direct au Sidecar 1) |
| `http://localhost:8002/` | API Serveur de Compétences (accès direct au Sidecar 2) |

### 5. Générer un Article de Blog

Une fois l'environnement en cours d'exécution et le port-forwarding actif, envoyez une requête `POST` au point de terminaison `/task` de l'Agent Copilot pour générer un article de blog.

**Via proxy inverse (recommandé) :**

```bash
curl -X POST http://localhost:8080/agent/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Écrivez un article de blog sur les modèles sidecar Kubernetes", "user_id": "mon-utilisateur"}'
```

**Via accès direct au sidecar :**

```bash
curl -X POST http://localhost:8001/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Écrivez un article de blog sur les modèles sidecar Kubernetes"}'
```

**Corps de la requête :**

| Champ | Type | Requis | Description |
|-------|------|----------|-------------|
| `task` | string | Oui | Le sujet du blog ou les instructions d'écriture |
| `user_id` | string | Non | Identifiant utilisateur (défaut à `"anonymous"`) |

**Ce qui se passe en coulisses :**
1. L'Agent Copilot crée une session en utilisant le SDK GitHub Copilot (modèle : `claude-sonnet-4.5`)
2. Il lit les directives SKILL.md synchronisées par le sidecar Serveur de Compétences
3. DeepSearch est utilisé pour rechercher le sujet en profondeur
4. Un fichier de blog Markdown est généré et sauvegardé dans le volume partagé `blog/` sous `blog-YYYY-MM-DD.md`

**Voir les blogs générés :**

| Action | URL / Commande |
|--------|---------------|
| Parcourir dans le navigateur | `http://localhost:8080/blog/` |
| Lister via API | `curl http://localhost:8080/agent/blogs` |
| Télécharger un fichier spécifique | `curl http://localhost:8080/agent/blog/blog-2026-02-25.md` |

> **Note :** La génération de blog peut prendre quelques minutes selon la complexité du sujet. Le point de terminaison `/task` retournera le contenu généré avec `blog_path` et `download_url` dans la réponse.

### 6. Nettoyage

```bash
make down          # Supprimer les ressources K8s
make cluster-down  # Supprimer le cluster kind
```

## Aperçu du Modèle Sidecar

Comparaison avec l'exemple Hello World `prototype/sidecar` :

| Fonctionnalité | Sidecar Hello World | Agent de Blog (Dual Sidecar) |
|------|--------------------|--------------------|
| Conteneur Principal | Nginx (page statique) | Nginx (Visionneuse de Blog + proxy inverse) |
| Sidecar 1 | Alpine (écriture périodique) | FastAPI + SDK Copilot (génération de contenu IA) |
| Sidecar 2 | — | Serveur de Compétences FastAPI (gestion des compétences) |
| Volumes Partagés | 1 emptyDir | 2 emptyDirs (blog-data + skills-shared) |
| Flux de Données | Sidecar → Principal | Compétence → Agent → Principal |
| Objectif | Démo sidecar écrivant des logs | Agent Copilot + Serveur de Compétences générant des blogs |

## Référence des Commandes Make

```bash
make install-tools-macos  # Installer kubectl, kind (macOS)
make install-tools-linux  # Installer kubectl, kind (Linux)
make doctor               # Vérification de l'environnement
make up                   # Déploiement en un clic
make status               # Vérifier le statut
make smoke                # Test de fumée
make port-forward         # Port forwarding
make logs                 # Logs du conteneur principal (blog-app)
make logs-copilot         # Logs du Sidecar 1 (copilot-agent)
make logs-skill           # Logs du Sidecar 2 (skill-server)
make set-token            # Définir le Jeton GitHub
make down                 # Supprimer les ressources K8s
make cluster-down         # Supprimer le cluster kind
```

## Déploiement Manuel

```bash
# Construire les images
docker build --platform linux/arm64 -t blog-agent-main:latest ./app
docker build --platform linux/arm64 -t blog-agent-copilot:latest ./sidecar
docker build --platform linux/arm64 -t blog-agent-skill:latest ./skill-sidecar

# Charger dans kind
kind load docker-image blog-agent-main:latest --name blog-agent-demo
kind load docker-image blog-agent-copilot:latest --name blog-agent-demo
kind load docker-image blog-agent-skill:latest --name blog-agent-demo

# Déployer
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Vérifier
kubectl get pods -l app=blog-agent
kubectl port-forward svc/blog-agent-svc 8080:80 8001:8001 8002:8002
```
