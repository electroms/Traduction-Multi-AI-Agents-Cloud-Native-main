# Dockerfile pour l'application Blog (conteneur principal - visionneuse web Nginx)

FROM nginx:1.27-alpine

# Copier la configuration Nginx personnalisée
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copier la page d'accueil
COPY index.html /usr/share/nginx/html/index.html

# Copier le script de surveillance
COPY monitor.sh /usr/local/bin/monitor.sh
RUN chmod +x /usr/local/bin/monitor.sh

# Créer le répertoire blog pour le point de montage du volume partagé
RUN mkdir -p /usr/share/nginx/html/blog

# Définir des labels pour identification et documentation
LABEL project="ghcli-blog-agent" \
      description="Blog App - Conteneur principal (visionneuse web Nginx)"

# Exposer le port web
EXPOSE 80

# Lancer Nginx et le script de surveillance
CMD sh -c '/usr/local/bin/monitor.sh & nginx -g "daemon off;"'
