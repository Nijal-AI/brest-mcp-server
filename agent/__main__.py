import logging
import httpx
import click
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from agent_executor import BrestAgentExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=10030)
def main(host, port):
  skill = AgentSkill(
    id="brest_skill",
    name="Brest tool",
    description="Obtenir des informations sur Brest",
    tags=["Brest", "culture", "histoire", "lieu", "événement"],
    examples=["Où se trouve la gare ?"],
    inputModes=["text"],
    outputModes=["text"],
  )
  
  capabilities = AgentCapabilities(
    streaming=True, pushNotifications=True
  )
  agent_card = AgentCard(
    name="Brest Expert Agent",
    description="Cet agent peut répondre à des questions sur les transports en commun, la météo, les événements et les alertes de service et retards de lignes de Brest.",
    url=f"http://{host}:{port}/",
    version="0.1.0",
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    capabilities=capabilities,
    skills=[skill]
  )
  logging.info(agent_card)

  # --8<-- [start:DefaultRequestHandler]
  httpx_client = httpx.AsyncClient()
  request_handler = DefaultRequestHandler(
      agent_executor=BrestAgentExecutor(),
      task_store=InMemoryTaskStore(),
      push_notifier=InMemoryPushNotifier(httpx_client),
  )
  server = A2AStarletteApplication(
      agent_card=agent_card, http_handler=request_handler
  )

  uvicorn.run(server.build(), host=host, port=port)
  # --8<-- [end:DefaultRequestHandler]

if __name__ == "__main__":
  main()
