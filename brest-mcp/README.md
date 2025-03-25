# Brest MCP  Server

Serveurle protocole MCP (Model Context Protocol) pour la région de Brest.

## Prérequis
- **Python** : 3.12.3 ou compatible
- **uv** : Gestionnaire de dépendances ([installation](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js** : Pour l'inspecteur MCP via `npx`

## Quickstart
1. **Installer uv** (si nécessaire) :
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
Windows version 
   ```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. **Cloner et lancer le serveur** :
   ```bash
   git clone https://github.com/BSE-dev/Brest-mcp-server.git
   cd Brest-mcp-server/brest-mcp
   uv venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   uv sync
   npx @modelcontextprotocol/inspector uv run brest-mcp
   ```
3. **Vérifier** : Ouvrez `http://localhost:5173` pour accéder à l'inspecteur MCP.

## Détails des étapes
### 1. Cloner le dépôt
```bash
git clone https://github.com/BSE-dev/Brest-mcp-server.git

cd Brest-mcp-server/brest-mcp
```
### 2. Créer et activer l’environnement
```bash
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 3. Installer les dépendances
```bash
uv sync
```

### 4. Lancer le serveur
```bash
npx @modelcontextprotocol/inspector uv run brest-mcp
```
- Proxy sur `port 3000`.
- Interface web : `http://localhost:5173`.

Exemple de sortie :
```
Starting MCP inspector...
Proxy server listening on port 3000
🔍 MCP Inspector is up and running at http://localhost:5173 🚀
```

## Résolution de problèmes
- **Erreur `ECONNREFUSED 127.0.0.1:3001`** : Vérifiez que `brest-mcp` écoute sur le port 3001 (SSE). Assurez-vous qu’il est lancé et que le port est libre.
- **Dépendances corrompues** : Supprimez `.venv` et `uv.lock`, puis relancez `uv venv` et `uv sync`.

## Notes
- Activez l’environnement avant de lancer le serveur pour utiliser les bonnes dépendances.
- Consultez `pyproject.toml` pour les dépendances spécifiques.

## Intrégration avec Claude Desktop

```json
{
  "allowDevTools": true,
  "mcpServers": {
    "brest-mcp": {
      "command": "[ABSOLUTE_PATH_TO_UV]",
      "args": [
        "--directory",
        "[ABSOLUTE_PATH_TO_REPO]/brest-mcp/brest-mcp",
        "run",
        "src/brest_mcp/server.py"
      ]
    }
  }
}
```

<!--  uv run src/brest_mcp/server.py -->
<!-- uvicorn brest-mcp:main -->