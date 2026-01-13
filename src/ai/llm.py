"""Ollama LLM integration for Aida."""

from dataclasses import dataclass, field
from typing import Sequence
import ollama
from ollama import ChatResponse

from src.core.config import OllamaConfig


"""Ollama LLM integration for Aida."""

from dataclasses import dataclass, field
from typing import Sequence, Callable, Any
import json
import ollama
from ollama import ChatResponse

from src.core.config import OllamaConfig


@dataclass
class Message:
    """A chat message."""

    role: str  # "user", "assistant", "system", or "tool"
    content: str
    images: list[str] = field(default_factory=list)  # Base64 encoded images
    tool_calls: list[Any] = field(default_factory=list)


class OllamaLLM:
    """Ollama LLM client for Aida."""

    def __init__(self, config: OllamaConfig):
        self.config = config
        self.client = ollama.Client(host=config.host)
        self.conversation_history: list[Message] = []
        self._memory_context: str | None = None
        self._tools: dict[str, Callable] = {}
        self._tool_definitions: list[dict] = []

        # Add system prompt
        self.conversation_history.append(
            Message(role="system", content=config.system_prompt)
        )

    def register_tool(self, func: Callable) -> None:
        """Register a python function as a tool for the LLM."""
        name = func.__name__
        self._tools[name] = func

    def set_memory_context(self, context: str | None) -> None:
        """Set memory context to inject into system prompt."""
        self._memory_context = context

    def chat(self, user_message: str, images: list[str] | None = None) -> str:
        """Send a message and get a response, handling tool calls automatically."""
        self.conversation_history.append(
            Message(role="user", content=user_message, images=images or [])
        )

        # Prepare tools list for Ollama
        available_tools = list(self._tools.values()) if self._tools else None

        # Loop to handle multiple tool calls if needed
        while True:
            messages = []
            for msg in self.conversation_history:
                content = msg.content

                # Inject memory context into system prompt
                if msg.role == "system":
                    if self._memory_context:
                        content = f"{content}\n\n## What you remember about this user:\n{self._memory_context}"
                    
                    # Nudge model to use tools if available
                    if self._tools:
                        content = f"{content}\n\n## Available Tools:\nYou have access to tools/functions. If a user asks something related to these tools (like checking the fridge or adding recipes), you MUST use the corresponding tool instead of guessing."

                msg_dict = {"role": msg.role, "content": content}
                if msg.images:
                    msg_dict["images"] = msg.images
                if msg.tool_calls:
                    msg_dict["tool_calls"] = msg.tool_calls
                messages.append(msg_dict)

            # Use vision model if images are provided (vision models often don't support tools yet)
            model = self.config.vision_model if images else self.config.model
            
            # If vision, disable tools to be safe
            current_tools = available_tools if not images else None

            print(f"DEBUG: Sending to LLM (Model: {model}). Tools enabled: {len(current_tools) if current_tools else 0}")

            response: ChatResponse = self.client.chat(
                model=model,
                messages=messages,
                options={"temperature": self.config.temperature},
                tools=current_tools,
            )

            message = response.message
            print(f"DEBUG: LLM Response content: '{message.content}'")
            print(f"DEBUG: LLM Tool calls: {message.tool_calls}")
            
            # --- NY LOGIKK: Sjekk om meldingen inneholder "falsk" JSON tool call ---
            if not message.tool_calls and "{" in (message.content or ""):
                try:
                    # Se etter mønsteret {"name": "...", "parameters": {...}}
                    import re
                    json_match = re.search(r'\{.*"name".*".*".*"parameters".*\{.*\}.*\}', message.content, re.DOTALL)
                    if json_match:
                        raw_json = json_match.group(0)
                        data = json.loads(raw_json)
                        if "name" in data and "parameters" in data:
                            print(f"DEBUG: Caught manual JSON tool call: {data['name']}")
                            # Lag et 'liksom' tool call objekt for å gjenbruke eksisterende logikk
                            class FakeFunc:
                                def __init__(self, n, a):
                                    self.name = n
                                    self.arguments = a
                            class FakeTool:
                                def __init__(self, n, a):
                                    self.function = FakeFunc(n, a)
                            
                            if not message.tool_calls:
                                message.tool_calls = []
                            message.tool_calls.append(FakeTool(data['name'], data['parameters']))
                            # Tøm innholdet så det ikke blir printet dobbelt
                            message.content = ""
                except Exception as e:
                    print(f"DEBUG: Failed to parse manual JSON: {e}")
            # --- SLUTT PÅ NY LOGIKK ---
            
            # Add assistant response to history
            self.conversation_history.append(
                Message(
                    role="assistant", 
                    content=message.content or "", 
                    tool_calls=message.tool_calls or []
                )
            )

            # If no tool calls, we are done
            if not message.tool_calls:
                return message.content

            # Handle tool calls
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = tool_call.function.arguments
                
                if fn_name in self._tools:
                    print(f"DEBUG: Executing tool '{fn_name}' with args: {fn_args}")
                    try:
                        func = self._tools[fn_name]
                        # Call the function
                        result = func(**fn_args)
                        result_str = str(result)
                        print(f"DEBUG: Tool '{fn_name}' returned: {result_str[:100]}...")
                    except Exception as e:
                        result_str = f"Error executing tool {fn_name}: {e}"
                        print(f"DEBUG: Tool '{fn_name}' failed: {e}")
                    
                    # Add tool output to history
                    self.conversation_history.append(
                        Message(role="tool", content=f"RESULTAT FRA VERKTØY {fn_name}: {result_str}\n\nINSTRUKSJON: Brukeren ser ikke dette resultatet ennå. Du MÅ nå svare brukeren og inkludere den relevante informasjonen fra dette resultatet i svaret ditt.")
                    )
                else:
                    self.conversation_history.append(
                        Message(role="tool", content=f"Error: Tool '{fn_name}' not found.")
                    )

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
