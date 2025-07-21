# Create server parameters for stdio connection
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv

load_dotenv()
async def process_query(query: str):
    try:
        print("Starting process_query...")
        client = MultiServerMCPClient(
            { "weather": {
                    # Ensure you start your weather server on port 8000
                    "url": "https://app-ff8b1b21-92e9-4638-9f06-5c1311ce97a3.cleverapps.io/mcp",
                    "transport": "streamable_http",
                },
            }
        )
        tools = await client.get_tools()
        print(f"Loaded {len(tools)} tools")
        model = AzureChatOpenAI(azure_deployment="gpt-4o-mini")  # Azure deployment name
        agent = create_react_agent(model, tools)
        print("Invoking the agent with the provided query...")
        try:
            agent_response = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
            print("Agent invocation successful.")
            print(agent_response)
            return agent_response
        except Exception as agent_error:
            print(f"Error during agent invocation: {str(agent_error)}")
            return {"messages": [{"content": "An error occurred while invoking the agent."}]}
    except Exception as e:
        print(f"Error in process_query: {str(e)}")
        return {"messages": [{"content": "An error occurred while processing your query."}]}

async def chat_loop():
    """Run an interactive chat loop"""
    print("\nMCP Client Started!")
    print("Type your queries or 'quit' to exit.")

    while True:
        try:
            query = input("\nQuery: ").strip()

            if query.lower() == "quit":
                break

            response = await process_query(query)
            print("\n" + response["messages"][-1].content)

        except Exception as e:
            print(f"\nError in chat_loop: {str(e)}")

async def main():
    try:
        await chat_loop()
    except Exception as e:
        print(f"Unhandled error in main: {str(e)}")


if __name__ == "__main__":
    import sys

    asyncio.run(main())
