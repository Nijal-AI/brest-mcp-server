import logging
import asyncio

from collections.abc import AsyncIterable
from typing import Any, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables.config import (
    RunnableConfig,
)
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent  # type: ignore
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

memory = MemorySaver()


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str


class BrestExpertAgent:

    SYSTEM_INSTRUCTION = (
        "Vous êtes un assistant expert de la ville de Brest. "
        "Votre rôle est de répondre aux questions sur Brest, sa culture, son histoire, ses lieux, ses événements, "
        "et d'aider les utilisateurs à obtenir des informations pertinentes sur la ville. "
        "Si la question ne concerne pas Brest ou ses environs, indiquez poliment que vous ne pouvez répondre qu'aux sujets liés à Brest."
    )

    RESPONSE_FORMAT_INSTRUCTION: str = (
        'Select status as completed if the request is complete'
        'Select status as input_required if the input is a question to the user'
        'Set response status to error if the input indicates an error'
    )

    async def get_tools(self):
        # Get and return tools from MCP server
        client = MultiServerMCPClient(
            {
                "brest": {
                    "command": "python",
                    "args": ["src/server.py", "stdio"],
                    "transport": "stdio",
                },
            }
        )
        tools = await client.get_tools()
        return tools
   
    def __init__(self):
        self.model = ChatAnthropic(model='claude-3-5-sonnet-20241022')
        tools=asyncio.run(self.get_tools())
        self.agent = create_react_agent(self.model, tools, checkpointer=memory,prompt=self.SYSTEM_INSTRUCTION,response_format=ResponseFormat,)

            
    async def stream(
        self, query: str, sessionId: str
    ) -> AsyncIterable[dict[str, Any]]:
        inputs: dict[str, Any] = {'messages': [('user', query)]}
        config: RunnableConfig = {'configurable': {'thread_id': sessionId}}
        async for item in self.agent.astream(inputs, config, stream_mode='values'):
            message = item['messages'][-1]
            if (
                isinstance(message, AIMessage)
                and message.tool_calls
                and len(message.tool_calls) > 0
            ):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': str(message),
                }
            elif isinstance(message, ToolMessage):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': str(message),
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config: RunnableConfig) -> dict[str, Any]:
        current_state = self.agent.get_state(config)

        structured_response = current_state.values.get('structured_response')
        if structured_response and isinstance(
            structured_response, ResponseFormat
        ):
            if structured_response.status in {'input_required', 'error'}:
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            if structured_response.status == 'completed':
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.message,
                }

        return {
            'is_task_complete': False,
            'require_user_input': True,
            'content': 'We are unable to process your request at the moment. Please try again.',
        }

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']
