import logging
import uuid
from typing import Any, Dict, Optional
from jarvis.tools.registry import registry

logger = logging.getLogger(__name__)

class PendingAction:
    def __init__(self, action_id: str, tool_name: str, args: Dict[str, Any], prompt_message: str):
        self.action_id = action_id
        self.tool_name = tool_name
        self.args = args
        self.prompt_message = prompt_message


class GuardrailsManager:
    def __init__(self):
        self.pending_action: Optional[PendingAction] = None

    def check_tool_safety(self, tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if a tool requires user confirmation.
        Returns confirmation prompt details if required, or None if safe to run immediately.
        """
        tool = registry.get_tool(tool_name)
        if not tool or not (tool.requires_confirmation or tool.dangerous):
            return None

        action_id = str(uuid.uuid4())[:8]

        # Generate a descriptive warning prompt based on the tool
        if tool_name == "delete_file":
            filepath = args.get("filepath", "the specified file")
            msg = f"I require your confirmation to permanently delete '{filepath}'. Shall I proceed?"
        elif tool_name == "system_power":
            action = args.get("action", "power change")
            msg = f"Executing system {action} will disrupt your workstation. Are you sure you want to proceed?"
        elif tool_name == "run_system_command":
            cmd = args.get("command", "")
            msg = f"Running terminal command '{cmd}' may modify system state. Do you authorize this action?"
        elif tool_name == "delete_calendar_event":
            msg = "Are you sure you want to cancel this calendar event?"
        elif tool_name == "delete_reminder":
            msg = "Are you sure you want to delete this reminder?"
        elif tool_name == "forget_fact":
            key = args.get("topic_or_key", "this information")
            msg = f"Are you sure you want me to forget '{key}'?"
        else:
            msg = f"Tool '{tool_name}' requires your authorization to proceed. Do you confirm?"

        self.pending_action = PendingAction(
            action_id=action_id,
            tool_name=tool_name,
            args=args,
            prompt_message=msg
        )

        return {
            "status": "requires_confirmation",
            "action_id": action_id,
            "tool_name": tool_name,
            "args": args,
            "message": msg,
            "dangerous": tool.dangerous
        }

    def has_pending_action(self) -> bool:
        return self.pending_action is not None

    def get_pending_action(self) -> Optional[PendingAction]:
        return self.pending_action

    def confirm(self) -> Dict[str, Any]:
        """Confirm and execute the pending action."""
        if not self.pending_action:
            return {"success": False, "error": "No pending action to authorize."}

        action = self.pending_action
        self.pending_action = None

        logger.info(f"User confirmed action {action.tool_name} with args {action.args}")
        exec_result = registry.execute(action.tool_name, **action.args)
        return {
            "success": True,
            "tool_name": action.tool_name,
            "result": exec_result.get("result"),
            "error": exec_result.get("error")
        }

    def cancel(self) -> Dict[str, Any]:
        """Cancel and reject the pending action."""
        if not self.pending_action:
            return {"success": False, "error": "No pending action to abort."}

        cancelled_tool = self.pending_action.tool_name
        self.pending_action = None
        return {
            "success": True,
            "cancelled_tool": cancelled_tool,
            "message": "Action cancelled. Safe state restored, Sir."
        }


# Global guardrails instance
guardrails = GuardrailsManager()