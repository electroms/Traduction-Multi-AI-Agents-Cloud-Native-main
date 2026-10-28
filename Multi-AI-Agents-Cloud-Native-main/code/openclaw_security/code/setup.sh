#!/usr/bin/env bash
# setup.sh — déploiement en une commande (édition sécurité renforcée)
set -euo pipefail

GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; BOLD="\033[1m"; RESET="\033[0m"
info()    { echo -e "${GREEN}[INFO]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
section() { echo -e "\n${BOLD}━━━  $*  ━━━${RESET}"; }
section "Étape 0 : Prérequis"
command -v docker >/dev/null 2>&1 || { error "docker introuvable"; exit 1; }
docker compose version >/dev/null 2>&1 || { error "docker compose v2 requis"; exit 1; }
info "Docker OK"

section "Étape 1 : Générer .env"
if [ ! -f .env ]; then
  TOKEN=$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))")
  sed "s/change_me_to_a_random_secret_string/${TOKEN}/" .env.example > .env
  info ".env créé (OPENCLAW_TOKEN utilisé en secours; token principal roté par secrets-init)"
else
  warn ".env existe déjà, passage"
fi

SERPAPI_KEY=$(grep SERPAPI_KEY .env | cut -d= -f2 | tr -d ' ')
if [ -z "$SERPAPI_KEY" ] || [ "$SERPAPI_KEY" = "your_serpapi_key_here" ]; then
  error "SERPAPI_KEY non configuré ! Éditez .env : https://serpapi.com/manage-api-key"
  exit 1
fi
info "SERPAPI_KEY configurée ✓"

section "Étape 2 : Permissions des répertoires"
mkdir -p config workspace output security
chmod 700 config       # openclaw.json contient des données sensibles
chmod 755 security
chmod +x security/egress-monitor.sh security/secrets-init.sh 2>/dev/null || true
info "Permissions des dossiers définies"

section "Étape 3 : Récupération des images (avec reprise)"
# Reprise automatique en cas d'échec TLS (jusqu'à 5 tentatives avec backoff croissant)
pull_with_retry() {
  local image="$1"
  local max=5
  for i in $(seq 1 $max); do
    info "Récupération de $image (tentative $i/$max)..."
    docker pull "$image" && return 0
    warn "Échec du pull, nouvelle tentative dans ${i}0 secondes..."
    sleep $((i * 10))
  done
  error "Échec de récupération de $image (tenté $max fois)"
  return 1
}

# Récupération séquentielle pour éviter la contention TLS simultanée
pull_with_retry alpine:3.19
pull_with_retry mvance/unbound:latest
pull_with_retry ollama/ollama:latest

section "Étape 4 : Démarrage des services"
info "Démarrage de tous les services..."
docker compose up -d --build

section "Étape 5 : Attente de la disponibilité des services"
info "Attente de la génération du token par secrets-init..."
for i in $(seq 1 20); do
  docker compose exec -T secrets-init test -f /run/secrets/gateway-token 2>/dev/null && {
    info "secrets-init prêt ✓ (token généré)"
    break
  }
  echo -n "."; sleep 2
done
echo ""

info "Attente de la disponibilité de dns-audit (Unbound)..."
for i in $(seq 1 20); do
  docker compose exec -T dns-audit dig @127.0.0.1 +short cloudflare.com >/dev/null 2>&1 && {
    info "dns-audit prêt ✓"
    break
  }
  echo -n "."; sleep 2
done
echo ""

info "Attente de la disponibilité d'Ollama..."
for i in $(seq 1 40); do
  docker compose exec -T ollama curl -fs http://localhost:11434/api/tags >/dev/null 2>&1 && {
    info "Ollama prêt ✓"
    break
  }
  echo -n "."; sleep 3
done
echo ""

section "Étape 6 : Récupérer le modèle"
docker compose run --rm model-init

section "Étape 7 : Installer le logging egress nftables sur l'hôte"
echo ""
warn "Recommandé : installer les règles d'audit egress nftables (équivalent microvm-egress) :"
echo "  sudo bash security/egress-monitor.sh setup"
echo ""
echo "  Après installation, surveillez en temps réel toutes les connexions sortantes de OpenClaw :"
echo "  sudo bash security/egress-monitor.sh watch"
echo ""

section "Terminé !"
echo ""
echo -e "${BOLD}Utilisation :${RESET}"
echo ""
echo "  # Exécution unique (entièrement automatique, sans interaction)"
echo "  docker compose run --rm podcast-app"
echo ""
echo "  # Mode planifié (toutes les 6 heures)"
echo "  docker compose run -d -e SCHEDULE_HOURS=6 --name scheduler podcast-app"
echo ""
echo "  # Voir uniquement les sujets tendances actuels"
echo "  docker compose run --rm podcast-app python auto_run.py --scout-only"
echo ""
echo -e "${BOLD}Surveillance de la sécurité :${RESET}"
echo ""
echo "  # Journal de requêtes DNS (audit Unbound)"
echo "  docker logs -f dns-audit"
echo ""
echo "  # Audit des accès au répertoire secrets"
echo "  docker logs -f secrets-init"
echo ""
echo "  # Journal des connexions egress (après installation)"
echo "  sudo bash security/egress-monitor.sh watch"
echo ""
echo -e "  Répertoire de sortie du podcast : ${BOLD}./output/${RESET}"
