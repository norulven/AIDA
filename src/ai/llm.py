"""Ollama LLM integration for Aida."""

from dataclasses import dataclass, field
from typing import Sequence
import ollama
from ollama import ChatResponse

from src.core.config import OllamaConfig


@dataclass
class Message:
    """A chat message."""

    role: str  # "user", "assistant", or "system"
    content: str
    images: list[str] = field(default_factory=list)  # Base64 encoded images


class OllamaLLM:
    """Ollama LLM client for Aida."""

    def __init__(self, config: OllamaConfig):
        self.config = config
        self.client = ollama.Client(host=config.host)
        self.conversation_history: list[Message] = []
        self._memory_context: str | None = None

        # Add system prompt
        self.conversation_history.append(
            Message(role="system", content=config.system_prompt)
        )

    def set_memory_context(self, context: str | None) -> None:
        """Set memory context to inject into system prompt."""
        self._memory_context = context

    def chat(self, user_message: str, images: list[str] | None = None) -> str:
        """Send a message and get a response.

        Args:
            user_message: The user's message
            images: Optional list of base64 encoded images
        """
        self.conversation_history.append(
            Message(role="user", content=user_message, images=images or [])
        )

        messages = []
        for msg in self.conversation_history:
            content = msg.content

            # Inject memory context into system prompt
            if msg.role == "system" and self._memory_context:
                content = f"{content}\n\n## What you remember about this user:\n{self._memory_context}"

            msg_dict = {"role": msg.role, "content": content}
            if msg.images:
                msg_dict["images"] = msg.images
            messages.append(msg_dict)

        # Use vision model if images are provided
        model = self.config.vision_model if images else self.config.model

        response: ChatResponse = self.client.chat(
            model=model,
            messages=messages,
            options={"temperature": self.config.temperature},
        )

        assistant_message = response.message.content
        self.conversation_history.append(
            Message(role="assistant", content=assistant_message)
        )

        return assistant_message

    def vision_chat(self, prompt: str, images: list[str]) -> str:
        """Send images to vision model for analysis (single-turn, no history).

        Args:
            prompt: What to analyze in the image(s)
            images: List of base64 encoded images

        Returns:
            Model's description/analysis of the images
        """
        response: ChatResponse = self.client.chat(
            model=self.config.vision_model,
            messages=[
                {"role": "user", "content": prompt, "images": images}
            ],
            options={"temperature": self.config.temperature},
        )

        return response.message.content

    def chat_stream(self, user_message: str):
        """Send a message and stream the response."""
        self.conversation_history.append(Message(role="user", content=user_message))

        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in self.conversation_history
        ]

        full_response = ""
        for chunk in self.client.chat(
            model=self.config.model,
            messages=messages,
            options={"temperature": self.config.temperature},
            stream=True,
        ):
            content = chunk.message.content
            full_response += content
            yield content

        self.conversation_history.append(
            Message(role="assistant", content=full_response)
        )

    def clear_history(self) -> None:
        """Clear conversation history, keeping system prompt."""
        system_msg = self.conversation_history[0]
        self.conversation_history = [system_msg]

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            self.client.list()
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List available models."""
        try:
            response = self.client.list()
            return [model.model for model in response.models]
        except Exception:
            return []
