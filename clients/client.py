import asyncio
import json
import os
import sys
from typing import Optional
from contextlib import AsyncExitStack
import requests
from dotenv import load_dotenv

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client  # Adjusted import path if the module structure differs
except ImportError:
    raise ImportError("The 'mcp' module or its submodules could not be resolved. Ensure it is installed and accessible.")

# Charger les variables d'environnement
load_dotenv()

# Configuration
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://192.168.1.106:11434/api/generate")
SERVER_SCRIPT_PATH = os.getenv("SERVER_SCRIPT_PATH", "/Users/Ibrahim/Documents/Dev/Brest-mcp-server/brest-mcp/src/brest_mcp/server.py")


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_script_path: str):
        """Connexion au serveur MCP via stdio."""
        if not server_script_path.endswith('.py'):
            raise ValueError("Le script serveur doit être un fichier .py")

        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # Lister les outils disponibles
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnecté au serveur avec les outils disponibles :", [tool.name for tool in tools])
        return tools

    async def call_ollama(self, prompt: str, tools: list) -> str:
        """Interroger LLaMA 3.2 via Ollama avec les outils disponibles."""
        tools_desc = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
        full_prompt = (
            f"Tu es un assistant utile. Voici la requête de l'utilisateur : '{prompt}'.\n"
            f"Tu as accès aux outils suivants du serveur MCP :\n{tools_desc}\n\n"
            "Si tu as besoin d'utiliser un outil, réponds au format JSON suivant :\n"
            "{\n"
            "    \"tool\": \"nom_de_l_outil\",\n"
            "    \"args\": { \"arg1\": \"valeur1\", ... }\n"
            "}"
        )

        payload = {"model": "llama3.2", "prompt": full_prompt, "stream": False}
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        result = response.json().get("response", "")
        return result

    async def process_query(self, query: str) -> str:
        """Traitement d'une requête avec LLaMA 3.2 et les outils MCP."""
        response = await self.session.list_tools()
        tools = response.tools
        ollama_response = await self.call_ollama(query, tools)

        try:
            tool_call = json.loads(ollama_response)
            if isinstance(tool_call, dict) and "tool" in tool_call:
                tool_name = tool_call["tool"]
                tool_args = tool_call.get("args", {})
                result = await self.session.call_tool(tool_name, tool_args)
                return f"Résultat de l'outil {tool_name} : {json.dumps(result.content, indent=2)}"
        except json.JSONDecodeError:
            return ollama_response

        return ollama_response

    async def chat_loop(self):
        """Boucle interactive pour le CLI."""
        print("\nClient MCP avec LLaMA 3.2 démarré !")
        print("Tapez vos requêtes ou 'quit' pour quitter.")

        while True:
            try:
                query = input("\nRequête : ").strip()
                if query.lower() == 'quit':
                    break
                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                print(f"\nErreur : {str(e)}")

    async def cleanup(self):
        """Nettoyer les ressources."""
        await self.exit_stack.aclose()


async def main():
    server_script = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(SERVER_SCRIPT_PATH)

    client = MCPClient()
    try:
        await client.connect_to_server(server_script)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
