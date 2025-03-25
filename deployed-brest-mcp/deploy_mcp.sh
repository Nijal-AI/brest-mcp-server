#!/bin/bash

# Configuration
MCP_PORT=8000
MCP_DIR="$(pwd)"
TUNNEL_NAME="brest-mcp-server"
ENV_FILE=".env"

# Couleurs pour les messages
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Démarrage du serveur MCP de Brest...${NC}"

# Vérifier si Python est installé
if ! command -v python &> /dev/null; then
    echo -e "${RED}Python n'est pas installé. Veuillez l'installer pour continuer.${NC}"
    exit 1
fi

# Vérifier si Cloudflared est installé
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}Cloudflared n'est pas installé. Veuillez l'installer pour continuer.${NC}"
    echo -e "${BLUE}Vous pouvez l'installer avec Homebrew : brew install cloudflare/cloudflare/cloudflared${NC}"
    exit 1
fi

# Vérifier si les dépendances Python sont installées
echo -e "${BLUE}Vérification des dépendances Python...${NC}"
if ! pip install -r requirements.txt; then
    echo -e "${RED}Erreur lors de l'installation des dépendances.${NC}"
    exit 1
fi

# Générer le fichier .env avec une clé JWT secrète si nécessaire
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${BLUE}Génération du fichier .env avec une clé JWT secrète...${NC}"
    JWT_SECRET=$(openssl rand -hex 32)
    echo "PORT=$MCP_PORT" > "$ENV_FILE"
    echo "HOST=0.0.0.0" >> "$ENV_FILE"
    echo "JWT_SECRET_KEY=$JWT_SECRET" >> "$ENV_FILE"
    echo -e "${GREEN}Fichier .env créé avec succès.${NC}"
else
    echo -e "${BLUE}Le fichier .env existe déjà.${NC}"
fi

# Vérifier si le tunnel existe déjà
if ! cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo -e "${BLUE}Création du tunnel Cloudflare '$TUNNEL_NAME'...${NC}"
    cloudflared tunnel create "$TUNNEL_NAME"
    
    # Récupérer l'ID du tunnel
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    
    # Configurer le DNS pour le tunnel
    echo -e "${BLUE}Configuration du DNS pour le tunnel...${NC}"
    echo -e "${BLUE}Votre serveur sera accessible à l'adresse: $TUNNEL_NAME.trycloudflare.com${NC}"
    cloudflared tunnel route dns "$TUNNEL_ID" "$TUNNEL_NAME.trycloudflare.com"
else
    echo -e "${BLUE}Le tunnel '$TUNNEL_NAME' existe déjà.${NC}"
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
fi

# Démarrer le serveur MCP en arrière-plan
echo -e "${BLUE}Démarrage du serveur MCP sur le port $MCP_PORT...${NC}"
cd "$MCP_DIR"
python app.py &
MCP_PID=$!

# Attendre que le serveur démarre
echo -e "${BLUE}Attente du démarrage du serveur...${NC}"
sleep 3

# Vérifier si le serveur a démarré correctement
if ! ps -p $MCP_PID > /dev/null; then
    echo -e "${RED}Le serveur MCP n'a pas démarré correctement.${NC}"
    exit 1
fi

echo -e "${GREEN}Serveur MCP démarré avec succès (PID: $MCP_PID)${NC}"

# Afficher les instructions pour utiliser le serveur
echo -e "${GREEN}=== INSTRUCTIONS POUR UTILISER LE SERVEUR MCP ===${NC}"
echo -e "${BLUE}1. Votre serveur MCP est accessible localement à l'adresse: http://localhost:$MCP_PORT${NC}"
echo -e "${BLUE}2. L'interface SSE est disponible à: http://localhost:$MCP_PORT/sse${NC}"
echo -e "${BLUE}3. Pour tester avec l'inspecteur MCP: npx @modelcontextprotocol/inspector${NC}"
echo -e "${BLUE}4. Pour utiliser avec Claude Desktop, ajoutez cette configuration:${NC}"
echo -e "${BLUE}   {
  \"mcpServers\": {
    \"brest-transport\": {
      \"command\": \"npx\",
      \"args\": [
        \"mcp-remote\",
        \"https://$TUNNEL_NAME.trycloudflare.com/sse\"
      ],
      \"auth\": {
        \"type\": \"oauth2\",
        \"clientId\": \"demo-client\",
        \"authorizationEndpoint\": \"https://$TUNNEL_NAME.trycloudflare.com/oauth/authorize\",
        \"tokenEndpoint\": \"https://$TUNNEL_NAME.trycloudflare.com/oauth/token\"
      }
    }
  }
}${NC}"

# Démarrer le tunnel Cloudflare
echo -e "${BLUE}Connexion du serveur MCP au tunnel Cloudflare...${NC}"
echo -e "${BLUE}Votre serveur MCP sera accessible via: https://$TUNNEL_NAME.trycloudflare.com${NC}"

# Exécuter cloudflared en premier plan
cloudflared tunnel run --url "http://localhost:$MCP_PORT" "$TUNNEL_NAME"

# Cette partie ne sera exécutée que si cloudflared est arrêté
echo -e "${BLUE}Arrêt du serveur MCP...${NC}"
kill $MCP_PID

echo -e "${GREEN}Déploiement terminé.${NC}"
