import asyncio
import os
from contextlib import AsyncExitStack
from dotenv import load_dotenv
import ollama
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

class MCPChatClient:
    """Client interactif se connectant à un serveur MCP et dialoguant avec LLaMA via Ollama."""
    def __init__(self):
        # Charger les variables d'environnement depuis .env
        load_dotenv()
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.messages = []  # Historique des messages de la conversation
        self.tools = []     # Description des outils MCP disponibles

    async def connect_to_server(self, server_script: str, *server_args):
        """Lance le serveur MCP en sous-processus et établit la connexion."""
        params = StdioServerParameters(
            command="python",
            args=[server_script, *server_args]
        )
        read_stream, write_stream = await self.exit_stack.enter_async_context(stdio_client(params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()
        resp = await self.session.list_tools()
        self.tools = [
            {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema} 
            for tool in resp.tools
        ]
        tool_names = [tool["name"] for tool in self.tools]
        print(f"✅ Connecté au serveur MCP. Outils disponibles : {tool_names}")

    async def process_query(self, query: str) -> str:
        """Envoie une requête utilisateur à LLaMA via Ollama et retourne la réponse finale."""
        self.messages.append({"role": "user", "content": query})
        
        # Préparer le message pour Ollama avec les outils disponibles
        system_prompt = "Vous êtes un assistant AI utilisant LLaMA 3.2. Voici les outils disponibles:\n"
        for tool in self.tools:
            system_prompt += f"- {tool['name']}: {tool['description']}\n"
        system_prompt += "Utilisez [tool_name: arguments] pour appeler un outil si nécessaire."

        messages = [
            {"role": "system", "content": system_prompt},
            *self.messages
        ]

        # Appel à Ollama
        response = ollama.chat(
            model="llama3.2",
            messages=messages
        )
        
        final_answer_parts = []
        content = response['message']['content']

        # Vérifier si LLaMA demande un outil (syntaxe simplifiée [tool_name: arguments])
        import re
        tool_pattern = r'\[(.*?):(.*?)\]'
        tool_match = re.search(tool_pattern, content)

        while tool_match:
            tool_name = tool_match.group(1).strip()
            tool_args = tool_match.group(2).strip()
            
            print(f"[Appel de l'outil {tool_name} avec les paramètres {tool_args}]")
            try:
                # Convertir les arguments en dictionnaire si possible
                import json
                tool_args_dict = json.loads(tool_args) if tool_args else {}
            except json.JSONDecodeError:
                tool_args_dict = {"input": tool_args} if tool_args else {}

            # Exécuter l'appel de l'outil
            result = await self.session.call_tool(tool_name, tool_args_dict)
            
            # Ajouter le texte avant l'appel d'outil
            pre_tool_text = content[:tool_match.start()].strip()
            if pre_tool_text:
                final_answer_parts.append(pre_tool_text)
            
            # Ajouter le résultat à l'historique
            self.messages.append({"role": "user", "content": result.content})
            
            # Nouvelle requête à Ollama avec le résultat
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": result.content})
            
            response = ollama.chat(
                model="llama3.2",
                messages=messages
            )
            content = response['message']['content']
            tool_match = re.search(tool_pattern, content)
        
        # Ajouter le contenu final
        if not tool_match:
            final_answer_parts.append(content)
        
        final_answer = "".join(final_answer_parts).strip()
        self.messages.append({"role": "assistant", "content": final_answer})
        return final_answer

    async def chat_loop(self):
        """Boucle interactive de chat avec l'utilisateur."""
        print("\n🗘 Démarrage du chat interactif MCP avec LLaMA 3.2 (tapez 'quit' pour quitter)")
        while True:
            try:
                query = input("\n➜ Votre question : ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n[Arrêt de la session]")
                break
            if query.lower() in {"quit", "exit", "q"}:
                print("[Fin de la conversation]")
                break
            if not query:
                continue
            try:
                answer = await self.process_query(query)
                print(f"\nLLaMA 🤖: {answer}")
            except Exception as e:
                print(f"\n[Erreur lors du traitement de la requête : {e}]")

    async def cleanup(self):
        """Nettoie et ferme toutes les ressources."""
        await self.exit_stack.aclose()

async def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "src", "mcp_gtfs", "server.py")
    print(f"Utilisation du serveur MCP depuis : {server_script}")

    client = MCPChatClient()
    try:
        await client.connect_to_server(server_script)
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())