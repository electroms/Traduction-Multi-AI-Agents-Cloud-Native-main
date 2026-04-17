#!/bin/bash
# Déploiement de gh-cli-blog-agent vers Azure Container Apps
# Ce script effectue :
# 1. Création d'un groupe de ressources
# 2. Création d'un registre de conteneurs Azure (ACR)
# 3. Build et push de l'image Docker vers l'ACR
# 4. Création d'un environnement Container Apps
# 5. Déploiement de l'application Container App avec le secret COPILOT_GITHUB_TOKEN

set -e

# Configuration (à personnaliser avant exécution)
RESOURCE_GROUP="Your Azure Resource Group"
LOCATION="Your Azure Region"
ACR_NAME="Your Azure Container Registry Name"
ENVIRONMENT="Your Container Apps Environment Name"
APP_NAME="Your Container App Name"
IMAGE_NAME="Your Docker Image Name"

# Secret - jeton GitHub Copilot (à remplacer par la variable réelle)
COPILOT_GITHUB_TOKEN="Your GitHub Token"

echo "=========================================="
echo "Déploiement de gh-cli-blog-agent vers Azure Container Apps"
echo "=========================================="
echo "Resource Group : $RESOURCE_GROUP"
echo "Région : $LOCATION"
echo "Container App : $APP_NAME"
echo "=========================================="

# Étape 1 : créer le groupe de ressources
echo ""
echo "Étape 1 : création du groupe de ressources..."
az group create --name $RESOURCE_GROUP --location $LOCATION -o table

# Étape 2 : créer le registre de conteneurs Azure
echo ""
echo "Étape 2 : création du registre Azure Container Registry (ACR)..."
az acr create --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true \
  -o table

# Récupérer les identifiants du registre ACR
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

echo "Serveur de connexion ACR : $ACR_LOGIN_SERVER"

# Étape 3 : builder et pousser l'image Docker dans ACR
echo ""
echo "Étape 3 : build et push de l'image Docker vers ACR..."
az acr build --registry $ACR_NAME \
  --image $IMAGE_NAME:latest \
  --file Dockerfile \
  .

# Étape 4 : créer l'environnement Container Apps
echo ""
echo "Étape 4 : création de l'environnement Container Apps..."
az containerapp env create \
  --name $ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  -o table

# Étape 5 : déployer l'application Container App avec secret
echo ""
echo "Étape 5 : déploiement de l'application Container App avec le secret COPILOT_GITHUB_TOKEN..."
az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --image "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest" \
  --registry-server $ACR_LOGIN_SERVER \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --target-port 8001 \
  --ingress external \
  --cpu 1 \
  --memory 2Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --secrets "copilot-github-token=$COPILOT_GITHUB_TOKEN" \
  --env-vars "COPILOT_GITHUB_TOKEN=secretref:copilot-github-token" "AGENT_PORT=8001" \
  -o table

# Récupérer le FQDN de l'application déployée
echo ""
echo "=========================================="
echo "Déploiement terminé avec succès !"
echo "=========================================="
APP_URL=$(az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)
echo "Votre application est disponible à : https://$APP_URL"
echo ""
echo "Pour afficher les logs :"
echo "  az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "Pour supprimer toutes les ressources :"
echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
