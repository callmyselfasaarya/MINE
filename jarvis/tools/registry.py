import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable,
        requires_confirmation: bool = False,
        dangerous: bool = False
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func
        self.requires_confirmation = requires_confirmation
        self.dangerous = dangerous

    def to_gemini_declaration(self) -> Dict[str, Any]:
        """Convert tool to Gemini API function declaration schema."""
        properties = {}
        required = []

        for param_name, param_info in self.parameters.items():
            param_type = param_info.get("type", "string").upper()
            if param_type == "INT":
                param_type = "INTEGER"
            elif param_type == "FLOAT":
                param_type = "NUMBER"
            elif param_type == "BOOL":
                param_type = "BOOLEAN"
            elif param_type == "DICT":
                param_type = "OBJECT"
            elif param_type == "LIST":
                param_type = "ARRAY"

            properties[param_name] = {
                "type": param_type,
                "description": param_info.get("description", "")
            }
            if param_info.get("required", False):
                required.append(param_name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": properties,
                "required": required
            }
        }

    def to_ollama_declaration(self) -> Dict[str, Any]:
        """Convert tool to Ollama / OpenAI function declaration schema."""
        properties = {}
        required = []

        for param_name, param_info in self.parameters.items():
            param_type = param_info.get("type", "string").lower()
            if param_type in ("int", "integer"):
                param_type = "integer"
            elif param_type in ("float", "number"):
                param_type = "number"
            elif param_type in ("bool", "boolean"):
                param_type = "boolean"
            elif param_type in ("dict", "object"):
                param_type = "object"
            elif param_type in ("list", "array"):
                param_type = "array"
            else:
                param_type = "string"

            properties[param_name] = {
                "type": param_type,
                "description": param_info.get("description", "")
            }
            if param_info.get("required", False):
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        requires_confirmation: bool = False,
        dangerous: bool = False
    ):
        def decorator(func: Callable):
            tool_def = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                func=func,
                requires_confirmation=requires_confirmation,
                dangerous=dangerous
            )
            self._tools[name] = tool_def
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        return dict(self._tools)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "requires_confirmation": t.requires_confirmation,
                "dangerous": t.dangerous
            }
            for t in self._tools.values()
        ]

    def get_gemini_declarations(self) -> List[Dict[str, Any]]:
        return [tool.to_gemini_declaration() for tool in self._tools.values()]

    def get_ollama_declarations(self) -> List[Dict[str, Any]]:
        return [tool.to_ollama_declaration() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """Execute a registered tool by name with arguments."""
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' is not recognized."}

        try:
            # Inspect func signature to pass only valid arguments
            sig = inspect.signature(tool.func)
            valid_kwargs = {}
            for k, v in kwargs.items():
                if k in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    valid_kwargs[k] = v

            result = tool.func(**valid_kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception(f"Error executing tool {name}")
            return {"success": False, "error": str(e)}


# Global registry instance
registry = ToolRegistry()
register_tool = registry.register
