"""Base agent class for CV Builder."""

import json
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

from src.llm.client import LLMClient
from src.llm.config import load_config

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):
    """Abstract base class for all CV Builder agents."""

    agent_name: str = "base"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        config: dict[str, Any] | None = None,
        agent_logger: Any | None = None,
    ):
        """Initialize the agent.

        Args:
            llm_client: LLM client instance. Creates one if not provided.
            config: Configuration dict. Loads from env if not provided.
            agent_logger: Optional logger for tracking LLM calls.
        """
        self.config = config or load_config()
        self.agent_logger = agent_logger
        self.llm_client = llm_client

        # Initialize LLM client lazily for LLM-backed agents.
        if self.llm_client is None and self.requires_llm:
            self.llm_client = LLMClient(
                agent_name=self.agent_name,
                config=self.config,
            )

    @property
    def requires_llm(self) -> bool:
        """Whether this agent requires an LLM.

        Override in subclasses that need LLM.
        """
        return False

    def build_messages(
        self,
        user_content: str,
        system_content: str | None = None,
    ) -> list[dict[str, str]]:
        """Build message list for LLM.

        Args:
            user_content: User message content.
            system_content: Optional system message.

        Returns:
            List of message dicts.
        """
        messages = []

        if system_content:
            messages.append({"role": "system", "content": system_content})

        messages.append({"role": "user", "content": user_content})

        return messages

    async def parse_json_response(self, response: str, model_class: type[T]) -> T:
        """Parse JSON response into Pydantic model.

        Args:
            response: Raw response string from LLM.
            model_class: Pydantic model class to parse into.

        Returns:
            Parsed model instance.

        Raises:
            ValueError: If response is not valid JSON.
        """
        # Extract JSON from markdown code blocks if present
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        try:
            data = json.loads(response)
            return model_class.model_validate(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse response: {e}")

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the agent's task.

        Subclasses must implement this method.
        """
        pass
