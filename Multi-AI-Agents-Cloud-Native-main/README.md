# Multi-Agents-IA-Cloud-Native

![bg](./imgs/bg.png)

Une collection d'**exemples d'applications multi-agents IA** conçues pour le **déploiement cloud-native** sur **Microsoft Azure**. Ce dépôt démontre comment construire, orchestrer et déployer des systèmes d'agents IA intelligents utilisant des technologies cloud modernes.

## Aperçu

Les systèmes multi-agents représentent l'évolution suivante des applications IA, où des agents spécialisés collaborent pour résoudre des tâches complexes. Ce dépôt fournit des exemples pratiques de construction de tels systèmes avec :

### Protocoles de Communication

- **Protocole Agent-to-Agent (A2A)** - Communication inter-agents utilisant JSON-RPC 2.0 et streaming SSE
- **Protocole de Contexte de Modèle (MCP)** - Protocole standardisé pour connecter les modèles IA à des sources de données externes et des outils
- **Protocole de Communication d'Agent (ACP)** - Protocole piloté par événements pour la messagerie asynchrone d'agents, supportant les modèles pub/sub et les workflows multi-agents complexes

### Frameworks et SDKs IA

- **SDK GitHub Copilot** - SDK multi-plateforme (Python, TypeScript, Go, .NET) pour intégrer les workflows agentiques de Copilot dans les applications. Expose le même runtime agent testé en production derrière Copilot CLI — vous définissez le comportement de l'agent, Copilot gère la planification, l'invocation d'outils, les modifications de fichiers, et plus
- **Microsoft Agent Framework** - Framework pour construire et orchestrer des agents IA
- **Microsoft Foundry** - Plateforme IA d'entreprise pour construire, déployer et gérer des applications IA à grande échelle

### Sécurité et Durcissement

- **Architecture de Défense en 5 Couches** - Sécurité complète des conteneurs avec rotation des secrets, audit DNS, profils seccomp, surveillance egress et liste d'autorisation des outils
- **Passerelle OpenClaw** - Passerelle d'agents IA avec authentification basée sur jetons, sandboxing d'outils et orchestration d'agents configurable

### Déploiement Cloud-Native sur Microsoft Azure

- **Azure Container Apps** - Plateforme de conteneurs serverless pour déployer des microservices et des agents IA avec mise à l'échelle automatique, équilibrage de charge intégré et opérations simplifiées
- **Azure Kubernetes Service (AKS)** - Kubernetes entièrement géré pour les déploiements multi-agents complexes nécessitant un contrôle fin, un réseau personnalisé et une orchestration d'entreprise
- **Azure Container Registry** - Registre Docker privé pour stocker et gérer les images de conteneurs
- **Azure API Management (APIM)** - Gestion complète du cycle de vie des API pour publier, sécuriser et surveiller les APIs d'agents IA avec limitation de débit intégrée, authentification et analyse

## Structure du Dépôt

```
Multi-AI-Agents-Cloud-Native/
├── README.md
└── code/
    ├── GitHubCopilotAgents_A2A/    # Exemple Multi-Agent avec Protocole A2A
    ├── GitHubCopilotSideCar/       # Exemple de Modèle Sidecar Kubernetes
    └── openclaw_security/          # Générateur de Podcast IA Sécurisé
```

---

## Exemples

### 1. Agents GitHub Copilot avec Protocole A2A

📁 **Emplacement** : [`code/GitHubCopilotAgents_A2A/`](./code/GitHubCopilotAgents_A2A/)

Un système d'orchestration multi-agent complet exploitant le **Protocole A2A** et le **SDK GitHub Copilot**.

#### Fonctionnalités Clés

| Fonctionnalité | Description |
|----------------|-------------|
| **Agent de Blog** | Génère des articles de blog techniques avec intégration DeepSearch |
| **Agent PPT** | Crée des présentations professionnelles avec des exemples de code |
| **Orchestrateur** | Route intelligemment les tâches utilisant Microsoft Agent Framework |
| **Protocole A2A** | Conformité complète JSON-RPC 2.0 + streaming SSE |

#### Points Forts de l'Architecture

- **Orchestration Multi-Agent** : Routage intelligent des tâches basé sur les capacités des agents et les mots-clés
- **Streaming en Temps Réel** : Événements Envoyés par le Serveur (SSE) pour les réponses de tâches de longue durée
- **Déploiement Cloud-Native** : Agents conteneurisés déployables sur Azure Container Apps
- **Configuration Sécurisée** : Gestion des secrets basée sur l'environnement

#### Technologies Utilisées

- Python 3.12+ avec FastAPI
- SDK GitHub Copilot
- Microsoft Agent Framework
- Azure Container Apps & Azure Container Registry
- Conteneurisation Docker

#### Démarrage Rapide

```bash
cd code/GitHubCopilotAgents_A2A

# Démarrer l'Agent de Blog
cd gh-copilot-multi-agents/gh-cli-blog-agent
pip install -r requirements.txt
python main.py

# Démarrer l'Agent PPT (nouveau terminal)
cd gh-copilot-multi-agents/gh-cli-ppt-agent
pip install -r requirements.txt
python main.py

# Démarrer l'Orchestrateur (nouveau terminal)
cd multi-agents-orchestrations/gh-copilot-a2a-orchestration
python main.py
```

👉 [Voir la Documentation Complète](./code/GitHubCopilotAgents_A2A/README.md)

---

### 2. Agent GitHub Copilot avec Modèle Sidecar Kubernetes

📁 **Emplacement** : [`code/GitHubCopilotSideCar/`](./code/GitHubCopilotSideCar/)

Un agent de génération de blog IA natif Kubernetes utilisant le **Modèle Dual-Sidecar**, déployant trois conteneurs dans un seul Pod pour la séparation des préoccupations et la collaboration par volume partagé.

#### Architecture

| Conteneur | Rôle | Port |
|-----------|------|------|
| **blog-app** (Principal) | Visionneuse web Nginx + proxy inverse | 80 |
| **copilot-agent** (Sidecar 1) | FastAPI + SDK GitHub Copilot pour génération de blog IA | 8001 |
| **skill-server** (Sidecar 2) | Gestion des compétences FastAPI, sert SKILL.md via ConfigMap | 8002 |

#### Fonctionnalités Clés

| Fonctionnalité | Description |
|----------------|-------------|
| **Modèle Dual-Sidecar** | Trois conteneurs dans un Pod — app principale, agent IA et serveur de compétences |
| **Collaboration par Volume Partagé** | Volumes `emptyDir` pour les données de blog et le partage de compétences entre conteneurs |
| **Compétences Pilotées par ConfigMap** | Comportement de l'agent défini dans ConfigMap Kubernetes, rechargable à chaud sans reconstruction |
| **SDK GitHub Copilot** | Génération de blog alimentée par IA avec intégration DeepSearch |
| **Proxy Inverse** | Nginx route `/agent/` et `/skill/` vers les sidecars via localhost |

#### Flux de Données

```
ConfigMap (SKILL.md) → Serveur de Compétences synchronise vers volume partagé
    → Agent Copilot lit les compétences & génère le blog
    → Écrit dans volume partagé → Nginx sert le contenu
```

#### Technologies Utilisées

- Python 3.12+ avec FastAPI
- SDK GitHub Copilot + Node.js 20
- Kubernetes (kind pour le développement local)
- Proxy inverse Nginx
- Pod multi-conteneurs Docker

#### Démarrage Rapide

```bash
cd code/GitHubCopilotSideCar/code/gh-cli-blog-agent

# Un clic : créer cluster, construire images, déployer
make up

# Définir votre jeton GitHub Copilot
make set-token TOKEN=<votre-jeton-github-copilot>

# Port-forward pour accéder à l'app
make port-forward

# Générer un article de blog
curl -X POST http://localhost:8080/agent/task \
  -H "Content-Type: application/json" \
  -d '{"topic": "Modèle Sidecar Kubernetes"}'

# Voir les blogs générés
curl http://localhost:8080/blog/
```

👉 [Voir la Documentation Complète](./code/GitHubCopilotSideCar/code/README.md)

---

### 3. Générateur de Podcast IA Sécurisé avec OpenClaw

📁 **Emplacement** : [`code/openclaw_security/`](./code/openclaw_security/)

Un pipeline entièrement automatisé de génération de podcast IA avec une architecture Docker Compose **durcie en 5 couches de sécurité**. Combine la **Passerelle OpenClaw** pour l'orchestration d'agents IA, **SerpAPI DeepSearch** pour l'exploration de tendances en temps réel, et **Ollama** pour la génération de dialogue LLM local — tout fonctionnant à l'intérieur de conteneurs durcis avec des contrôles de sécurité en profondeur.

#### Architecture

| Conteneur | Rôle | Couche de Sécurité |
|-----------|------|-------------------|
| **secrets-init** | Rotation des jetons au démarrage, volume secrets tmpfs, audit inotifywait | Couche 0 |
| **dns-audit** | Sidecar DNS Unbound, toutes les requêtes journalisées, upstream Cloudflare DoT | Couche 1 |
| **openclaw** | Passerelle d'agents IA avec profil seccomp, cap_drop ALL, liste d'autorisation des outils | Couches 2–5 |
| **ollama** | Inférence LLM locale (Qwen3-0.6B) | Sécurité héritée |
| **podcast-app** | Pipeline automatisé : exploration tendances → recherche web → génération dialogue LLM → sortie TXT | Sécurité héritée |

#### Fonctionnalités Clés

| Fonctionnalité | Description |
|----------------|-------------|
| **Défense en 5 Couches** | Rotation des secrets, audit DNS, profils seccomp, journalisation egress nftables, liste d'autorisation des outils |
| **Pipeline Automatisé** | De bout en bout : exploration des tendances → recherche web → génération de dialogue LLM → sortie TXT |
| **OpenClaw TrendScout** | Agent IA utilise des outils `web_search` pour découvrir des sujets tendance IA/tech en temps réel |
| **SerpAPI DeepSearch** | Recherche Google + scraping de pages + résumé LLM pour construire une base de connaissances approfondie |
| **Inférence LLM Locale** | Ollama avec Qwen3-0.6B pour la génération privée et gratuite de scripts de podcast |
| **Rotation des Jetons de Boot** | Jeton de passerelle régénéré à chaque démarrage de conteneur via `secrets-init` |
| **Audit des Requêtes DNS** | Toutes les résolutions DNS journalisées via sidecar Unbound pour une visibilité complète |
| **Durcissement seccomp** | Profil personnalisé autorise AF_NETLINK (requis Node.js) tout en bloquant les évasions d'espaces de noms CLONE_NEWUSER |

#### Architecture de Sécurité

```
┌─────────────────────────────────────────────────────────────┐
│  Hôte (journalisation egress nftables, IMDS bloqué)         │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ secrets-init │  │  dns-audit   │  │     openclaw     │  │
│  │ (Couche 0)   │  │  (Couche 1)  │  │ (Couches 2-5)    │  │
│  │ rotation     │  │ DNS Unbound  │  │ profil seccomp   │  │
│  │ boot         │  │ log-queries  │  │ cap_drop ALL     │  │
│  │ inotifywait  │  │ Cloudflare   │  │ liste outils     │  │
│  │ audit log    │  │ DoT upstream │  │ exec désactivé   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │ secrets-vol     │ :53               │            │
│         └─────────────────┴───────────────────┘            │
│                    podcast-net (172.20.0.0/24)              │
└─────────────────────────────────────────────────────────────┘
```

#### Flux de Données

```
secrets-init (rotation jeton) → Passerelle OpenClaw (authentifie)
    → Agent TrendScout (web_search via SerpAPI) → découvre sujets tendance
    → DeepSearch (scrape & résume sources) → construit base connaissances
    → LLM Ollama (génère dialogue podcast) → sortie TXT
```

#### Technologies Utilisées

- Python 3.11 avec pipeline d'orchestration automatisé
- Passerelle OpenClaw pour la gestion d'agents IA
- Ollama avec Qwen3-0.6B pour l'inférence LLM locale
- SerpAPI pour la recherche web en temps réel
- Docker Compose avec architecture de sécurité multi-conteneurs
- Unbound DNS pour l'audit des requêtes
- Profils seccomp personnalisés pour le filtrage des appels système

#### Démarrage Rapide

```bash
cd code/openclaw_security/code

# Configurer votre clé SerpAPI
cp .env.example .env
vim .env  # remplir SERPAPI_KEY

# Configuration & lancement en une commande
chmod +x setup.sh && ./setup.sh
docker compose run --rm podcast-app
```

#### Surveillance

```bash
# Audit des requêtes DNS (tous les domaines résolus par OpenClaw)
docker logs -f dns-audit

# Audit d'accès au répertoire secrets
docker logs -f secrets-init

# Journalisation des connexions egress au niveau hôte
sudo bash security/egress-monitor.sh setup
sudo bash security/egress-monitor.sh watch
```

👉 [Voir la Documentation Complète](./code/openclaw_security/README.md)

---

## Prérequis

Avant d'exécuter tout exemple, assurez-vous d'avoir :

- **Python** : 3.12 ou supérieur
- **Node.js** : 20 ou supérieur
- **Docker** : Pour le déploiement conteneurisé
- **Docker Compose** : v2 requis pour l'exemple de sécurité OpenClaw
- **Azure CLI** : Pour les déploiements Azure
- **kubectl** : Pour les déploiements Kubernetes
- **kind** : Pour les clusters Kubernetes locaux (exemple Sidecar)
- **Clé SerpAPI** : Pour DeepSearch dans le générateur de podcast ([obtenir une clé](https://serpapi.com/manage-api-key))
- **Git** : Pour le contrôle de version

## Services Azure Utilisés

| Service | Objectif |
|---------|----------|
| **Azure Container Apps** | Hébergement de conteneurs serverless pour les agents |
| **Azure Kubernetes Service (AKS)** | Kubernetes géré pour les déploiements de modèle Sidecar |
| **Azure Container Registry** | Stockage d'images Docker privées |
| **Groupes de Ressources Azure** | Organisation et gestion des ressources |

## Ressources Associées

### Documentation

- [Spécification du Protocole A2A](https://a2a-protocol.org/latest/)
- [SDK GitHub Copilot](https://github.com/github/copilot-sdk)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Documentation Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Documentation Azure Kubernetes Service](https://learn.microsoft.com/en-us/azure/aks/)
- [Conteneurs Sidecar Kubernetes](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
- [Profils de Sécurité seccomp Docker](https://docs.docker.com/engine/security/seccomp/)
- [Résolveur DNS Unbound](https://nlnetlabs.nl/projects/unbound/about/)
- [Documentation SerpAPI](https://serpapi.com/search-api)
- [Ollama](https://ollama.com/)

### Tutoriels

- [Documentation FastAPI](https://fastapi.tiangolo.com/)
- [Démarrage Docker](https://docs.docker.com/get-started/)
- [Meilleures Pratiques de Sécurité Docker Compose](https://docs.docker.com/compose/use-secrets/)

---

## Contribution

Les contributions sont les bienvenues ! Si vous avez un exemple multi-agent à ajouter :

1. Créez un nouveau dossier sous `code/`
2. Incluez un `README.md` complet avec architecture, configuration et instructions d'utilisation
3. Fournissez des scripts de déploiement pour Azure
4. Soumettez une pull request

## Licence

Ce projet est open source et disponible sous la [Licence MIT](LICENSE).

## Auteur

**Kinfey Lo** - [GitHub](https://github.com/kinfey)

---

> 💡 **Astuce** : Mettez une étoile à ce dépôt pour rester à jour avec de nouveaux exemples multi-agents !