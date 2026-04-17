#!/usr/bin/env bash
# egress-monitor.sh — Journalisation des connexions sortantes (egress)
#
# Correspond à la journalisation egress nftables dans ryoooo/microvm-openclaw.nix :
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
# Version Docker : installe des règles nftables/iptables équivalentes sur l'hôte pour le bridge podcast-net.
# Doit être exécuté en root après "docker-compose up".
#
# Usage :
#   sudo bash security/egress-monitor.sh setup    # installer les règles de journalisation egress
#   sudo bash security/egress-monitor.sh teardown # supprimer les règles
#   sudo bash security/egress-monitor.sh watch    # surveillance en direct via journalctl grep
#   sudo bash security/egress-monitor.sh status   # afficher l'état des règles

set -euo pipefail

LOG_PREFIX="podcast-egress: "     # préfixe utilisé dans les logs syslog
TABLE="podcast_egress"              # nom de la table nftables
CHAIN="podcast_fwd"                # nom de la chaîne nftables
NETWORK_NAME="ai-podcast-v2_podcast-net"   # nom du réseau docker (depuis docker network ls)

# ── Fonctions utilitaires ────────────────────────────────────────
get_bridge_iface() {
  # Essayez de récupérer le nom exact de l'interface du réseau docker
  local net_id
  net_id=$(docker network inspect "$NETWORK_NAME" --format '{{.Id}}' 2>/dev/null || \
           docker network ls --filter name=podcast-net -q 2>/dev/null | head -1)
  if [ -n "$net_id" ]; then
    echo "br-${net_id:0:12}"
  else
    # repli : scanner les interfaces br- existantes
    ip link show | grep -oP 'br-[a-f0-9]{12}' | head -1 || echo "docker0"
  fi
}

cmd_setup() {
  local iface
  iface=$(get_bridge_iface)
  echo "[egress-monitor] Interface bridge cible : $iface"

  if command -v nft &>/dev/null; then
    echo "[egress-monitor] Mode nftables activé..."

    # Idempotent : supprimer d'abord l'ancienne table si elle existe
    nft delete table inet "$TABLE" 2>/dev/null || true

    # Créer la table + la chaîne (équivalent à type filter hook forward priority 10)
    nft add table inet "$TABLE"
    nft add chain inet "$TABLE" "$CHAIN" \
      '{ type filter hook forward priority 10; policy accept; }'

    # Règle 1 : journaliser toutes les nouvelles connexions depuis le réseau podcast
    nft add rule inet "$TABLE" "$CHAIN" \
      iifname "$iface" ct state new \
      log prefix "\"${LOG_PREFIX}\"" \
      accept

    # Règle 2 : bloquer l'accès au daemon Docker de l'hôte (prévenir l'évasion de conteneur)
    nft add rule inet "$TABLE" "$CHAIN" \
      iifname "$iface" ip daddr 172.17.0.1 tcp dport 2376 drop

    # Règle 3 : bloquer les services metadata cloud (IMDS AWS/GCP/Azure, vol de credentials)
    nft add rule inet "$TABLE" "$CHAIN" \
      iifname "$iface" ip daddr 169.254.169.254 drop

    echo "[egress-monitor] ✓ règles nftables installées"
    nft list table inet "$TABLE"

  else
    echo "[egress-monitor] nftables indisponible, fallback iptables..."

    # Règle de journalisation iptables (effet équivalent)
    iptables -I FORWARD 1 \
      -i "$iface" \
      -m conntrack --ctstate NEW \
      -j LOG --log-prefix "$LOG_PREFIX" --log-level 6 2>/dev/null || \
    iptables -I FORWARD 1 \
      -i "$iface" -m state --state NEW \
      -j LOG --log-prefix "$LOG_PREFIX" 2>/dev/null

    # Bloquer l'accès au daemon Docker de l'hôte
    iptables -I FORWARD 2 \
      -i "$iface" -d 172.17.0.1 -p tcp --dport 2376 -j DROP 2>/dev/null || true

    # Bloquer le service metadata
    iptables -I FORWARD 3 \
      -i "$iface" -d 169.254.169.254 -j DROP 2>/dev/null || true

    echo "[egress-monitor] ✓ règles iptables installées (mode fallback)"
  fi

  echo ""
  echo "[egress-monitor] Commandes de surveillance :"
  echo "  sudo journalctl -f | grep '${LOG_PREFIX}'"
  echo "  sudo bash security/egress-monitor.sh watch"
}

cmd_teardown() {
  if command -v nft &>/dev/null; then
    nft delete table inet "$TABLE" 2>/dev/null && \
      echo "[egress-monitor] ✓ règles nftables supprimées" || \
      echo "[egress-monitor] règles introuvables, rien à supprimer"
  else
    local iface
    iface=$(get_bridge_iface)
    iptables -D FORWARD -i "$iface" -m conntrack --ctstate NEW \
      -j LOG --log-prefix "$LOG_PREFIX" --log-level 6 2>/dev/null || true
    iptables -D FORWARD -i "$iface" -d 172.17.0.1 -p tcp --dport 2376 -j DROP 2>/dev/null || true
    iptables -D FORWARD -i "$iface" -d 169.254.169.254 -j DROP 2>/dev/null || true
    echo "[egress-monitor] ✓ règles iptables supprimées"
  fi
}

cmd_watch() {
  echo "=== Surveillance en direct des connexions egress OpenClaw ==="
  echo "=== Mode équivalent microvm-egress (Ctrl+C pour quitter) ==="
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
  echo "=== Règles nftables ==="
  if command -v nft &>/dev/null; then
    nft list table inet "$TABLE" 2>/dev/null || echo "(règles non installées)"
  fi
  echo ""
  echo "=== Chaîne FORWARD iptables ==="
  iptables -L FORWARD -n -v 2>/dev/null | grep -E "($LOG_PREFIX|169.254|2376)" || echo "(aucune règle correspondante)"
}

case "${1:-help}" in
  setup)    cmd_setup ;;
  teardown) cmd_teardown ;;
  watch)    cmd_watch ;;
  status)   cmd_status ;;
  *)
    echo "Usage: sudo bash security/egress-monitor.sh <setup|teardown|watch|status>"
    echo ""
    echo "  setup    — installer les règles de journalisation nftables/iptables (équivalent microvm-egress)"
    echo "  teardown — supprimer les règles"
    echo "  watch    — surveillance en direct des connexions egress (journalctl grep)"
    echo "  status   — afficher l'état actuel des règles"
    ;;
esac
