import asyncio
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from anthropic import AsyncAnthropic
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

class MCPChatClient:
    """Client interactif se connectant à un serveur MCP et dialoguant avec Claude."""
    def __init__(self):
        # Charger la clé API Anthropic depuis le .env dans les variables d'env
        load_dotenv()
        # Initialiser le client Claude (utilisera ANTHROPIC_API_KEY depuis l'environnement)
        self.anthropic = AsyncAnthropic()
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.messages = []  # Historique des messages de la conversation
        self.tools = []     # Description des outils MCP disponibles

    async def connect_to_server(self, server_script: str, *server_args):
        """Lance le serveur MCP en sous-processus et établit la connexion."""
        # Préparer les paramètres pour une connexion via STDIO au script serveur
        params = StdioServerParameters(
            command="python",
            args=[server_script, *server_args]
        )
        # Démarrer le serveur MCP et obtenir les flux I/O
        read_stream, write_stream = await self.exit_stack.enter_async_context(stdio_client(params))
        # Créer la session MCP avec les flux du serveur
        self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        # Initialiser la session (handshake MCP)
        await self.session.initialize()
        # Récupérer la liste des outils disponibles sur le serveur
        resp = await self.session.list_tools()
        # Stocker la liste des outils sous forme de dict (nom, description, schéma)
        self.tools = [
            {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema} 
            for tool in resp.tools
        ]
        # Message de confirmation
        tool_names = [tool["name"] for tool in self.tools]
        print(f"✅ Connecté au serveur MCP. Outils disponibles : {tool_names}")

    async def process_query(self, query: str) -> str:
        """Envoie une requête utilisateur à Claude et retourne la réponse finale."""
        # Ajouter le message utilisateur à l'historique
        self.messages.append({"role": "user", "content": query})
        # Appel initial à l'API Claude avec les messages et la liste d'outils disponibles
        response = await self.anthropic.messages.create(
            model="claude-3-5-latest",   # on utilise la dernière version de Claude 3.5 (par exemple)
            messages=self.messages,
            tools=self.tools,
            max_tokens=1000
        )
        # Accumulateur pour le texte de réponse à afficher
        final_answer_parts = []
        # Boucler tant que Claude demande des outils et qu'on lui fournit les résultats
        while True:
            # Parcourir les blocs de la réponse (texte et/ou demande d'outil)
            tool_request = None
            for content in response.content:
                if content.type == 'text':
                    # Accumuler les segments de texte générés
                    if content.text:
                        final_answer_parts.append(content.text)
                elif content.type == 'tool_use':
                    # Claude souhaite utiliser un outil
                    tool_request = content
                    break  # on sort de la boucle pour traiter l'outil
            if tool_request is None:
                # Aucune demande d'outil dans la réponse, on a donc une réponse finale
                break
            # Si on a détecté un outil à appeler
            tool_name = tool_request.name
            tool_args = tool_request.input
            print(f"[Appel de l'outil {tool_name} avec les paramètres {tool_args}]")
            # Exécuter l'appel de l'outil via la session MCP
            result = await self.session.call_tool(tool_name, tool_args)
            # Ajouter éventuellement la pensée/texte associé (si fourni par Claude avant l'appel)
            if hasattr(tool_request, 'text') and tool_request.text:
                # Considérer le texte précédent l'appel outil comme réponse partielle
                self.messages.append({"role": "assistant", "content": tool_request.text})
            # Ajouter le résultat de l'outil comme message utilisateur (entrée pour Claude)
            self.messages.append({"role": "user", "content": result.content})
            # Reprendre la conversation en interrogeant à nouveau Claude avec le résultat
            response = await self.anthropic.messages.create(
                model="claude-3-5-latest",
                messages=self.messages,
                max_tokens=1000
            )
            # puis boucle à nouveau pour vérifier si Claude veut un autre outil
            continue
        # Joindre tous les segments de texte collectés comme réponse finale
        final_answer = "".join(final_answer_parts).strip()
        # Ajouter la réponse finale de Claude à l'historique des messages (rôle assistant)
        self.messages.append({"role": "assistant", "content": final_answer})
        return final_answer

    async def chat_loop(self):
        """Boucle interactive de chat avec l'utilisateur."""
        print("\n🗘 Démarrage du chat interactif MCP (tapez 'quit' pour quitter)")
        while True:
            try:
                query = input("\n➜ Votre question : ").strip()
            except (EOFError, KeyboardInterrupt):
                # En cas de Ctrl+C ou fermeture de l'entrée, on quitte proprement
                print("\n\n[Arrêt de la session]")
                break
            if query.lower() in {"quit", "exit", "q"}:
                print("[Fin de la conversation]")
                break
            if not query:
                continue  # ignorer les entrées vides
            # Traiter la requête utilisateur via Claude et outils MCP
            try:
                answer = await self.process_query(query)
                # Afficher la réponse de Claude
                print(f"\nClaude 🤖: {answer}")
            except Exception as e:
                print(f"\n[Erreur lors du traitement de la requête : {e}]")

    async def cleanup(self):
        """Nettoie et ferme toutes les ressources (session MCP, processus, etc.)."""
        # Fermer la session et le processus serveur MCP via l'ExitStack
        await self.exit_stack.aclose()


async def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "src", "mcp_gtfs", "server.py")
    print(f"Utilisation du serveur MCP depuis : {server_script}")

    client = MCPChatClient()
    try:
        # Connexion au serveur MCP
        await client.connect_to_server(server_script)
        # Lancer la boucle interactive
        await client.chat_loop()
    finally:
        # Nettoyage des ressources
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
