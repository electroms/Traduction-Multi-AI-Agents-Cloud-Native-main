#!/usr/bin/env bash
# egress-monitor.sh — Journalisation des connexions sortantes
#
# Correspond à la journalisation nftables egress dans ryoooo/microvm-openclaw.nix :
#
#   networking.nftables.tables.microvm-egress = {
#     family = "inet";
#     content = ''
#       chain forward {
#         type filter hook forward priority 10; policy accept;
#         iifname "microbr" ct state new log prefix "microvm-egress: " accept
#       }
#     '';
#   };
#
# Version Docker : installe des règles nftables/iptables équivalentes sur l’hôte
# pour le bridge podcast-net.
# Doit être exécuté en root après docker-compose up.
#
# Usage :
#   sudo bash security/egress-monitor.sh setup    # installer les règles de journalisation
#   sudo bash security/egress-monitor.sh teardown # supprimer les règles
#   sudo bash security/egress-monitor.sh watch    # surveillance en temps réel (journalctl grep)
#   sudo bash security/egress-monitor.sh status   # afficher les règles en place

set -euo pipefail

LOG_PREFIX="podcast-egress: "     # préfixe syslog, correspond à microvm-egress
TABLE="podcast_egress"
CHAIN="podcast_fwd"
NETWORK_NAME="ai-podcast-v2_podcast-net"   # nom du réseau docker (docker network ls)

# ── Fonctions utilitaires ─────────────────────────────────────────
get_bridge_iface() {
  # Tenter d'obtenir le nom exact de l'interface via docker network inspect
  local net_id
  net_id=$(docker network inspect "$NETWORK_NAME" --format '{{.Id}}' 2>/dev/null || \
           docker network ls --filter name=podcast-net -q 2>/dev/null | head -1)
  if [ -n "$net_id" ]; then
    echo "br-${net_id:0:12}"
  else
    # fallback: scan existing br- interfaces
    ip link show | grep -oP 'br-[a-f0-9]{12}' | head -1 || echo "docker0"
  fi
}

cmd_setup() {
  local iface
  iface=$(get_bridge_iface)
  echo "[egress-monitor] Interface bridge ciblée : $iface"

  if command -v nft &>/dev/null; then
    echo "[egress-monitor] Mode nftables..."

    # Idempotence : suppression de l’ancienne table si elle existe
    nft delete table inet "$TABLE" 2>/dev/null || true

    # Create table + chain (corresponds to type filter hook forward priority 10)
    nft add table inet "$TABLE"
    nft add chain inet "$TABLE" "$CHAIN" \
      '{ type filter hook forward priority 10; policy accept; }'

    # Règle 1 : journaliser toutes les nouvelles connexions depuis le réseau podcast
    # (équivalent principal à microvm-egress)
    nft add rule inet "$TABLE" "$CHAIN" \
      iifname "$iface" ct state new \
      log prefix "\"${LOG_PREFIX}\"" \
      accept

    # Règle 2 : bloquer l’accès au démon Docker de l’hôte (éviter l’évasion de conteneur)
    nft add rule inet "$TABLE" "$CHAIN" \
      iifname "$iface" ip daddr 172.17.0.1 tcp dport 2376 drop

    # Règle 3 : bloquer les services de métadonnées cloud (AWS/GCP/Azure IMDS,
    # éviter le vol de credentials)
    nft add rule inet "$TABLE" "$CHAIN" \
      iifname "$iface" ip daddr 169.254.169.254 drop

    echo "[egress-monitor] \u2713 nftables rules installed"
    nft list table inet "$TABLE"

  else
    echo "[egress-monitor] nftables non disponible, utilisation du fallback iptables..."

    # Règle iptables LOG (effet équivalent)
    iptables -I FORWARD 1 \
      -i "$iface" \
      -m conntrack --ctstate NEW \
      -j LOG --log-prefix "$LOG_PREFIX" --log-level 6 2>/dev/null || \
    iptables -I FORWARD 1 \
      -i "$iface" -m state --state NEW \
      -j LOG --log-prefix "$LOG_PREFIX" 2>/dev/null

    # Bloquer le démon Docker de l’hôte
    iptables -I FORWARD 2 \
      -i "$iface" -d 172.17.0.1 -p tcp --dport 2376 -j DROP 2>/dev/null || true

    # Bloquer le service de métadonnées cloud
    iptables -I FORWARD 3 \
      -i "$iface" -d 169.254.169.254 -j DROP 2>/dev/null || true

    echo "[egress-monitor] \u2713 règles iptables installées (mode fallback)"
  fi

  echo ""
  echo "[egress-monitor] Monitor commands:"
  echo "  sudo journalctl -f | grep '${LOG_PREFIX}'"
  echo "  sudo bash security/egress-monitor.sh watch"
}

cmd_teardown() {
  if command -v nft &>/dev/null; then
    nft delete table inet "$TABLE" 2>/dev/null && \
      echo "[egress-monitor] \u2713 règles nftables supprimées" || \
      echo "[egress-monitor] règles non trouvées, rien à supprimer"
  else
    local iface
    iface=$(get_bridge_iface)
    iptables -D FORWARD -i "$iface" -m conntrack --ctstate NEW \
      -j LOG --log-prefix "$LOG_PREFIX" --log-level 6 2>/dev/null || true
    iptables -D FORWARD -i "$iface" -d 172.17.0.1 -p tcp --dport 2376 -j DROP 2>/dev/null || true
    iptables -D FORWARD -i "$iface" -d 169.254.169.254 -j DROP 2>/dev/null || true
    echo "[egress-monitor] \u2713 règles iptables supprimées"
  fi
}

cmd_watch() {
  echo "=== Surveillance en direct des connexions sortantes OpenClaw ==="
  echo "=== mode équivalent microvm-egress (Ctrl+C pour quitter) ==="
  echo ""
  journalctl -f --output=short-monotonic 2>/dev/null | \
    grep --line-buffered "$LOG_PREFIX" | \
    while IFS= read -r line; do
      echo "$(date '+%H:%M:%S') $line"
    done
}

cmd_status() {
  local iface
  iface=$(get_bridge_iface)
  echo "=== Interface bridge : $iface ==="
  ip link show "$iface" 2>/dev/null || echo "(interface introuvable, exécutez d'abord docker compose up)"
  echo ""
  echo "=== règles nftables ==="
  if command -v nft &>/dev/null; then
    nft list table inet "$TABLE" 2>/dev/null || echo "(règles non installées)"
  fi
  echo ""
  echo "=== chaîne FORWARD iptables ==="
  iptables -L FORWARD -n -v 2>/dev/null | grep -E "($LOG_PREFIX|169.254|2376)" || echo "(aucune règle correspondante)"
}

case "${1:-help}" in
  setup)    cmd_setup ;;
  teardown) cmd_teardown ;;
  watch)    cmd_watch ;;
  status)   cmd_status ;;
  *)
    echo "Usage : sudo bash security/egress-monitor.sh <setup|teardown|watch|status>"
    echo ""
    echo "  setup    \u2014 installer les règles nftables/iptables de journalisation egress (équivalent microvm-egress)"
    echo "  teardown \u2014 supprimer les règles"
    echo "  watch    \u2014 surveillance en direct des connexions sortantes (journalctl grep)"
    echo "  status   \u2014 afficher le statut des règles en place"
    ;;
esac
