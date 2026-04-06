#!/usr/bin/env sh
# secrets-init.sh — rotation du token + audit au démarrage
#
# 1. Régénère gateway-token à chaque démarrage de conteneur et écrit dans tmpfs /run/secrets/
# 2. inotifywait surveille /run/secrets pour tous les événements d'accès (journal d'audit)

set -e

SECRETS_DIR="/run/secrets"
TOKEN_FILE="$SECRETS_DIR/gateway-token"
AUDIT_LOG="$SECRETS_DIR/audit.log"

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"  # restreindre l'accès au répertoire des secrets

# ── 1. Régénération du token gateway à chaque démarrage ─────────────────────
echo "[secrets-init] Génération d'un nouveau token gateway..."

NEW_TOKEN=$(cat /proc/sys/kernel/random/uuid 2>/dev/null | tr -d '-' || \
            head -c 32 /dev/urandom | xxd -p | head -c 48)

# ── 1a. Synchroniser le token dans openclaw.json AVANT d'écrire gateway-token ─
# Doit être fait avant l'écriture du fichier de healthcheck pour éviter qu'OpenClaw
# démarre avec l'ancien token et accepte des requêtes signées par le nouveau.
OPENCLAW_CONFIG="/openclaw-config/openclaw.json"
if command -v jq >/dev/null 2>&1 && [ -f "$OPENCLAW_CONFIG" ]; then
  jq --arg tok "$NEW_TOKEN" '.gateway.auth.token = $tok' "$OPENCLAW_CONFIG" > /tmp/oc.tmp
  mv /tmp/oc.tmp "$OPENCLAW_CONFIG"
  echo "[secrets-init] Token synchronisé dans openclaw.json"
else
  echo "[secrets-init] WARNING: jq ou $OPENCLAW_CONFIG introuvable, synchronisation openclaw.json ignorée"
fi

# ── 1b. Écrire gateway-token (cible du healthcheck — après la sync jq) ─
echo "$NEW_TOKEN" > "$TOKEN_FILE"
chmod 400 "$TOKEN_FILE"

echo "[secrets-init] Token écrit dans $TOKEN_FILE ($(wc -c < $TOKEN_FILE) bytes)"

# openclaw.json lit auth.token depuis ce fichier
echo "OPENCLAW_GATEWAY_TOKEN=$NEW_TOKEN" > "$SECRETS_DIR/gateway.env"
chmod 400 "$SECRETS_DIR/gateway.env"

# ── 2. Surveiller le répertoire secrets avec inotifywait ──────────────────
if command -v inotifywait >/dev/null 2>&1; then
  echo "[secrets-init] Démarrage de la surveillance d'audit du répertoire secrets..."
  (
    echo "$(date -Iseconds) [audit] surveillance du répertoire secrets démarrée" >> "$AUDIT_LOG"
    inotifywait -m -r --format '%T %e %w%f' --timefmt '%Y-%m-%dT%H:%M:%S' \
      -e access -e modify -e open -e create -e delete -e attrib \
      "$SECRETS_DIR" 2>/dev/null | while read -r line; do
        echo "[secrets-audit] $line" | tee -a "$AUDIT_LOG"
    done
  ) &
  echo "[secrets-init] PID du moniteur d'audit : $!"
else
  echo "[secrets-init] inotifywait non disponible, surveillance d'audit ignorée"
fi

echo "[secrets-init] Initialisation des secrets terminée"
echo "[secrets-init] TOKEN (8 premiers caractères) : ${NEW_TOKEN%${NEW_TOKEN#????????}}..."
