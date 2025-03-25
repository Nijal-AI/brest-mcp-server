# Deployed Brest MCP Server

Ce projet est une version déployable du serveur MCP (Model Context Protocol) de Brest, qui fournit des informations en temps réel sur les transports publics à Brest via le protocole JSON-RPC 2.0.

## Fonctionnalités

- Serveur MCP conforme au protocole Model Context Protocol (JSON-RPC 2.0)
- Authentification via GitHub OAuth
- Support des requêtes SSE (Server-Sent Events) pour les mises à jour en temps réel
- API JSON-RPC pour l'accès aux données de transport public
- Interface web simple pour l'authentification et l'accès aux données

## Prérequis

- Python 3.8 ou supérieur
- Un compte GitHub pour la configuration OAuth
- Un compte sur une plateforme de déploiement (Heroku, Cloudflare, PythonAnywhere, etc.)

## Installation locale

1. Clonez ce dépôt :
```bash
git clone <URL_DU_DEPOT>
cd deployed-brest-mcp
```

2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

3. Créez un fichier `.env` à la racine du projet avec les variables d'environnement suivantes :
```
GITHUB_CLIENT_ID=votre_client_id
GITHUB_CLIENT_SECRET=votre_client_secret
SECRET_KEY=votre_cle_secrete
GTFS_VEHICLE_POSITIONS_URL=https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-vehicle-position
GTFS_TRIP_UPDATES_URL=https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-trip-update
GTFS_SERVICE_ALERTS_URL=https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-alerts
GTFS_REFRESH_INTERVAL=30
MCP_HOST=localhost
MCP_PORT=8000
NETWORK=bibus
```

4. Lancez l'application :
```bash
python app.py
```

L'application sera accessible à l'adresse http://localhost:8000.

## Configuration OAuth GitHub

1. Créez une nouvelle application OAuth sur GitHub :
   - Accédez à [GitHub Developer Settings](https://github.com/settings/developers)
   - Cliquez sur "New OAuth App"
   - Remplissez les informations :
     - Application name : Brest MCP Server
     - Homepage URL : URL de votre application (ex: http://localhost:8000 pour le développement local)
     - Authorization callback URL : URL de callback (ex: http://localhost:8000/authorize)

2. Après avoir créé l'application, notez l'ID client et le secret client pour les utiliser dans vos variables d'environnement.

## Déploiement

### Heroku

1. Créez une application Heroku :
```bash
heroku create brest-mcp-server
```

2. Configurez les variables d'environnement :
```bash
heroku config:set GITHUB_CLIENT_ID=votre_id_client
heroku config:set GITHUB_CLIENT_SECRET=votre_secret_client
heroku config:set SECRET_KEY=votre_cle_secrete
heroku config:set GTFS_VEHICLE_POSITIONS_URL=https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-vehicle-position
heroku config:set GTFS_TRIP_UPDATES_URL=https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-trip-update
heroku config:set GTFS_SERVICE_ALERTS_URL=https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-alerts
heroku config:set GTFS_REFRESH_INTERVAL=30
heroku config:set NETWORK=bibus
```

3. Déployez l'application :
```bash
git push heroku main
```

### Autres plateformes

Ce projet peut être déployé sur n'importe quelle plateforme supportant Python et Flask, comme PythonAnywhere, Cloudflare Workers, Google Cloud Run, etc. Consultez la documentation de votre plateforme préférée pour les instructions spécifiques.

## Utilisation

Une fois déployé, votre serveur MCP sera accessible via les endpoints suivants :

- `/` : Page d'accueil avec lien de connexion
- `/login` : Redirection vers GitHub pour l'authentification
- `/sse` : Endpoint SSE pour les mises à jour en temps réel
- `/api` : Endpoint JSON-RPC pour les requêtes API

## Test avec l'inspecteur MCP

Vous pouvez tester votre serveur MCP déployé avec l'inspecteur MCP :

```bash
npx @modelcontextprotocol/inspector@latest
```

Ouvrez l'inspecteur dans votre navigateur à l'adresse http://localhost:5173, puis entrez l'URL de votre serveur MCP (ex: https://votre-app.herokuapp.com/sse) et cliquez sur "Connect".

## Licence

[Insérer votre licence ici]
