#!/bin/sh
set -eu

BLOG_DIR="/usr/share/nginx/html/blog"
STATUS_FILE="${BLOG_DIR}/sidecar-status.txt"

# Assurer que le r�pertoire de blog existe
mkdir -p "$BLOG_DIR"

# Enregistrer le d�marrage du sidecar
echo "blog-viewer sidecar d�marr� � $(date)" > "$STATUS_FILE"

while true; do
  # Compter les fichiers markdown du blog
  BLOG_COUNT=$(find "$BLOG_DIR" -name "blog-*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "[$(date)] battement sidecar | fichiers blog : ${BLOG_COUNT}" >> "$STATUS_FILE"

  # �viter que le fichier de statut ne devienne trop volumineux (conserver les 100 derni�res lignes)
  if [ "$(wc -l < "$STATUS_FILE")" -gt 100 ]; then
    tail -50 "$STATUS_FILE" > "${STATUS_FILE}.tmp" && mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
  fi

  # Attendre 10 secondes avant le prochain cycle
  sleep 10
done
