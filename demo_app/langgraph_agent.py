"""LangGraph ReAct agent wrapping existing account chatbot tools."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, interrupt
from langgraph.errors import GraphInterrupt

from . import chatbot as chatbot_tools
from .agents.context import current_account_id
from .billing import pay_outstanding_statements
from .models import Account

try:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_checkpointer = MemorySaver()
_agent = None

SYSTEM_PROMPT = """You are a helpful T-Mobile customer service assistant for the current account.
You are the only agent that talks to the customer. Two specialists work behind you; they return facts, and you rewrite those facts in plain language.

Available services:
- 1_day: 1 Day International Pass ($1, 512MB data)
- 10_day: 10 Day International Pass ($35, 5GB data)
- 30_day: 30 Day International Pass ($50, 15GB data)
- international_pass: Any international pass (will choose best option)

Route questions:
- Bill, amount due, due immediately, due date, taxes, statement, line items, "why was I charged", payment guidance → ask_billing_agent.
- Device dispatched, order status, shipping, ETA, "when will it ship", "where is my device" → ask_sap_agent (read-only). Only Ordered lines have dispatch/ETA. If SAP returns a pending order, the device has not shipped yet. Never tell the customer it was already dispatched unless the specialist says it is Shipped or dispatched=true. You cannot mark a device as dispatched; warehouse staff do that in SAP. Do not mention Active lines.
- Activate a shipped device/line → activate_shipped_lines (only after SAP dispatch; Ordered lines cannot be activated).
- List/suspend/restore/reactivate lines, add/mirror/upgrade line, add a service → your existing line tools.
- Pay the bill → pay_account (never let a specialist take payment).

You may say you checked billing or the order/dispatch system. Never mention MCP, specialists by internal name, or tools.

When users mention line identifiers, extract them carefully - they could be employee names, phone numbers, line names, or employee numbers.

If a request is ambiguous, call the tool anyway; the tool will ask for clarification or open a modal. Do not invent line IDs.

If the user says "add a service" without naming which pass, call add_service_to_lines with an empty service_type so the Add Service modal opens.

Write actions (suspend, restore, reactivate, activate a shipped line, adding a named service, paying the bill) are confirmed in the UI after you call the tool. Call the tool rather than asking them to type yes/no. Do not claim the write already succeeded until a tool result says it did.

If ask_sap_agent reports the order/dispatch system is unavailable, tell the customer you could not reach that system right now.

account_id is injected automatically; you do not need to ask for it.
"""


def _account_id() -> int:
    account_id = current_account_id.get()
    if not account_id:
        raise ValueError("Account ID is not set for this chatbot turn")
    return account_id


def _confirm_then(action: str, preview: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    decision = interrupt({"action": action, "preview": preview})
    approved = True
    if isinstance(decision, dict):
        approved = bool(decision.get("approved", False))
    elif decision is False:
        approved = False
    if not approved:
        return {
            "success": False,
            "cancelled": True,
            "error": "Cancelled. No changes were made.",
        }
    return fn()


def _as_list(value: Optional[List[str]]) -> Optional[List[str]]:
    if not value:
        return None
    return [str(item) for item in value if item]


@tool
def list_account_lines(status_filter: Optional[str] = None) -> dict:
    """List all phone lines in the account with details and services."""
    return chatbot_tools.list_account_lines(_account_id(), status_filter)


@tool
def get_account_summary() -> dict:
    """Get comprehensive account information, line counts, and amount due."""
    result = chatbot_tools.get_account_summary(_account_id())
    try:
        account = Account.objects.get(id=_account_id())
        result["amount_due"] = float(account.amount_due)
        result["due_immediately"] = float(account.due_immediately)
    except Account.DoesNotExist:
        pass
    return result


@tool
def add_line_to_account(
    line_name: Optional[str] = None,
    employee_name: Optional[str] = None,
    employee_number: Optional[str] = None,
) -> dict:
    """Open the Add A Line modal for this account."""
    return chatbot_tools.add_line_to_account(
        _account_id(), line_name, employee_name, employee_number
    )


@tool
def mirror_line(line_identifier: Optional[str] = None) -> dict:
    """Open the Mirror Line modal, optionally preselecting a line."""
    return chatbot_tools.mirror_line(_account_id(), line_identifier)


@tool
def upgrade_line(line_identifier: Optional[str] = None) -> dict:
    """Open the Upgrade Line modal, optionally preselecting a line."""
    return chatbot_tools.upgrade_line(_account_id(), line_identifier)


@tool
def add_service_to_lines(
    service_type: Optional[str] = None,
    line_identifiers: Optional[List[str]] = None,
) -> dict:
    """Add an international pass or other service to one or more lines. Empty service_type opens the Add Service modal."""
    identifiers = _as_list(line_identifiers)
    if not service_type or not str(service_type).strip():
        return chatbot_tools.add_service_to_lines(_account_id(), service_type, identifiers)

    lines_label = ", ".join(identifiers) if identifiers else "all matching lines"
    preview = (
        f"Add service '{service_type}' to {lines_label} on this account. "
        "Taxes will be applied. Confirm to continue."
    )
    return _confirm_then(
        "add_service_to_lines",
        preview,
        lambda: chatbot_tools.add_service_to_lines(_account_id(), service_type, identifiers),
    )


@tool
def suspend_lines(line_identifiers: Optional[List[str]] = None) -> dict:
    """Suspend one or more active lines."""
    identifiers = _as_list(line_identifiers)
    lines_label = ", ".join(identifiers) if identifiers else "the applicable active line(s)"
    preview = f"Suspend {lines_label}. Service will be temporarily disabled. Confirm to continue."
    return _confirm_then(
        "suspend_lines",
        preview,
        lambda: chatbot_tools.suspend_lines(_account_id(), identifiers),
    )


@tool
def restore_lines(line_identifiers: Optional[List[str]] = None) -> dict:
    """Restore one or more suspended lines."""
    identifiers = _as_list(line_identifiers)
    lines_label = ", ".join(identifiers) if identifiers else "all suspended lines"
    preview = f"Restore {lines_label} to active service. Confirm to continue."
    return _confirm_then(
        "restore_lines",
        preview,
        lambda: chatbot_tools.restore_lines(_account_id(), identifiers),
    )


@tool
def reactivate_cancelled_lines(line_identifiers: Optional[List[str]] = None) -> dict:
    """Reactivate one or more cancelled lines."""
    identifiers = _as_list(line_identifiers)
    lines_label = ", ".join(identifiers) if identifiers else "all cancelled lines"
    preview = f"Reactivate {lines_label}. Confirm to continue."
    return _confirm_then(
        "reactivate_cancelled_lines",
        preview,
        lambda: chatbot_tools.reactivate_cancelled_lines(_account_id(), identifiers),
    )


@tool
def activate_shipped_lines(line_identifiers: Optional[List[str]] = None) -> dict:
    """Activate a shipped line after SAP dispatch. Ordered lines cannot be activated yet."""
    identifiers = _as_list(line_identifiers)
    account = Account.objects.get(id=_account_id())
    if identifiers:
        candidates = chatbot_tools._find_lines(account, identifiers)
        shipped = [line for line in candidates if line.status == 'SHIPPED']
        if not shipped:
            statuses = ", ".join(sorted({line.get_status_display() for line in candidates})) or "none"
            return {
                "success": False,
                "error": f"Only Shipped lines can be activated. Found: {statuses}",
            }
    else:
        shipped = list(account.lines.filter(status='SHIPPED'))
        if not shipped:
            return {"success": False, "error": "No shipped lines found to activate."}
    lines_label = ", ".join(identifiers) if identifiers else ", ".join(line.line_name for line in shipped)
    preview = f"Activate {lines_label}. Status will change from Shipped to Active. Confirm to continue."
    return _confirm_then(
        "activate_shipped_lines",
        preview,
        lambda: chatbot_tools.activate_shipped_lines(_account_id(), identifiers),
    )


@tool
def pay_account() -> dict:
    """Pay all unpaid and past-due billing statements for this account."""
    account = Account.objects.get(id=_account_id())
    amount_due = account.amount_due
    if amount_due <= 0:
        return {
            "success": True,
            "message": "No balance due",
            "amount_due": 0.0,
            "statements_paid": 0,
            "total_paid": 0.0,
        }
    preview = f"Pay ${amount_due:.2f} now (unpaid billing statements). Confirm to continue."
    return _confirm_then(
        "pay_account",
        preview,
        lambda: pay_outstanding_statements(Account.objects.get(id=_account_id())),
    )


@tool
def ask_billing_agent(question: str) -> dict:
    """Ask the billing specialist about amount due, statements, taxes, line items, or why a bill is high. Read-only; does not take payment."""
    from .agents.billing_agent import run_billing_agent

    return run_billing_agent(question, _account_id())


@tool
def ask_sap_agent(question: str) -> dict:
    """Ask the SAP order specialist whether a device has been dispatched and when it will ship."""
    from .agents.sap_agent import run_sap_agent

    return run_sap_agent(question, _account_id())


TOOLS = [
    list_account_lines,
    get_account_summary,
    add_service_to_lines,
    suspend_lines,
    restore_lines,
    reactivate_cancelled_lines,
    activate_shipped_lines,
    add_line_to_account,
    mirror_line,
    upgrade_line,
    pay_account,
    ask_billing_agent,
    ask_sap_agent,
]


def _get_agent():
    global _agent
    if _agent is None:
        api_key = getattr(settings, "OPENAI_API_KEY", None) or None
        model = ChatOpenAI(model="gpt-4", temperature=0.3, api_key=api_key)
        _agent = create_react_agent(
            model,
            TOOLS,
            checkpointer=_checkpointer,
            prompt=SYSTEM_PROMPT,
        )
    return _agent


def _interrupt_payload(result: Any) -> Optional[Dict[str, Any]]:
    interrupts = None
    if isinstance(result, dict):
        interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict):
        return value
    return {"action": "confirm", "preview": str(value)}


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def _parse_tool_payload(content: Any) -> Dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not content:
        return {}
    text = str(content)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"raw": text}


def _format_result(function_name: str, tool_result: Dict[str, Any], fallback: str) -> Dict[str, Any]:
    if tool_result.get("cancelled"):
        return {
            "response": "Cancelled. No changes were made.",
            "tool_result": None,
            "refresh_needed": False,
        }

    if function_name in ("ask_billing_agent", "ask_sap_agent"):
        return {
            "response": fallback or tool_result.get("summary") or "Here is what I found.",
            "tool_result": None,
            "refresh_needed": False,
        }

    if function_name == "activate_shipped_lines":
        if tool_result.get("lines_activated"):
            return {
                "response": fallback or f"Activated {tool_result.get('lines_activated')} line(s).",
                "tool_result": "\n".join(tool_result.get("results") or []),
                "refresh_needed": True,
            }
        return {
            "response": tool_result.get("error") or fallback or "No shipped lines were activated.",
            "tool_result": None,
            "refresh_needed": False,
        }

    if function_name == "pay_account":
        if tool_result.get("statements_paid"):
            total = tool_result.get("total_paid", 0)
            return {
                "response": f"✅ Paid ${float(total):.2f}. Amount due is now ${float(tool_result.get('amount_due', 0)):.2f}.",
                "tool_result": tool_result.get("message"),
                "refresh_needed": True,
            }
        return {
            "response": tool_result.get("message") or "There is no balance due.",
            "tool_result": None,
            "refresh_needed": False,
        }

    formatted = chatbot_tools.chatbot._format_function_response(function_name, tool_result, fallback)
    if not formatted.get("response") and fallback:
        formatted["response"] = fallback
    return formatted


def _result_from_messages(messages: List[Any]) -> Dict[str, Any]:
    last_ai = ""
    last_tool_name = None
    last_tool_payload: Dict[str, Any] = {}

    for message in messages:
        if isinstance(message, AIMessage):
            text = _message_content(message).strip()
            if text:
                last_ai = text
        if isinstance(message, ToolMessage):
            last_tool_name = getattr(message, "name", None) or last_tool_name
            last_tool_payload = _parse_tool_payload(message.content)

    if last_tool_name and last_tool_payload:
        formatted = _format_result(last_tool_name, last_tool_payload, last_ai)
        if not formatted.get("response"):
            formatted["response"] = last_ai or "Done."
        return formatted

    return {
        "response": last_ai or "I can help with lines, services, and billing for this account.",
        "tool_result": None,
        "refresh_needed": False,
    }


def _has_pending_interrupt(agent, config) -> bool:
    try:
        state = agent.get_state(config)
    except Exception:
        return False
    interrupts = getattr(state, "interrupts", None)
    if interrupts:
        return True
    for task in getattr(state, "tasks", None) or ():
        if getattr(task, "interrupts", None):
            return True
    return False


def _clear_pending_interrupt(agent, config) -> None:
    """Finish a paused tool call so the thread is valid for a new user message."""
    if not _has_pending_interrupt(agent, config):
        return
    try:
        agent.invoke(Command(resume={"approved": False}), config)
    except GraphInterrupt:
        pass
    except Exception:
        logger.exception("Failed to clear pending chatbot confirmation")


def process_message(
    message: str,
    account_id: int,
    conversation_history: List[Dict] = None,
    thread_id: Optional[str] = None,
    resume: Optional[str] = None,
) -> Dict[str, Any]:
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key or api_key == "your_openai_api_key_here":
        return {
            "response": "OpenAI API key not configured. Please set your API key in settings.py",
            "tool_result": None,
            "refresh_needed": False,
            "thread_id": thread_id,
            "pending_confirmation": None,
        }

    thread_id = thread_id or f"account-{account_id}"
    config = {"configurable": {"thread_id": thread_id}}
    token = current_account_id.set(account_id)

    try:
        agent = _get_agent()
        if resume in ("approve", "reject"):
            if not _has_pending_interrupt(agent, config):
                return {
                    "response": "There is no pending action to confirm.",
                    "tool_result": None,
                    "refresh_needed": False,
                    "thread_id": thread_id,
                    "pending_confirmation": None,
                }
            payload = Command(resume={"approved": resume == "approve"})
        else:
            # A new utterance while Confirm is waiting would leave a tool_call
            # without a ToolMessage. Cancel the pending write first.
            _clear_pending_interrupt(agent, config)
            payload = {"messages": [HumanMessage(content=message or "")]}

        try:
            result = agent.invoke(payload, config)
        except GraphInterrupt as exc:
            pending = None
            args = exc.args[0] if exc.args else None
            if isinstance(args, (list, tuple)) and args:
                first = args[0]
                pending = getattr(first, "value", first)
            elif isinstance(args, dict):
                pending = args
            if isinstance(pending, dict):
                return {
                    "response": "Please confirm this action before I make any changes.",
                    "tool_result": pending.get("preview"),
                    "refresh_needed": False,
                    "thread_id": thread_id,
                    "pending_confirmation": {
                        "action": pending.get("action"),
                        "preview": pending.get("preview") or "Confirm this action?",
                    },
                }
            raise
        pending = _interrupt_payload(result)
        if pending:
            return {
                "response": "Please confirm this action before I make any changes.",
                "tool_result": pending.get("preview"),
                "refresh_needed": False,
                "thread_id": thread_id,
                "pending_confirmation": {
                    "action": pending.get("action"),
                    "preview": pending.get("preview") or "Confirm this action?",
                },
            }

        messages = result.get("messages") if isinstance(result, dict) else []
        formatted = _result_from_messages(messages or [])
        formatted["thread_id"] = thread_id
        formatted["pending_confirmation"] = None
        return formatted
    except Exception as exc:
        logger.exception("LangGraph chatbot error")
        return {
            "response": f"I encountered an error processing your request: {exc}",
            "tool_result": None,
            "refresh_needed": False,
            "thread_id": thread_id,
            "pending_confirmation": None,
        }
    finally:
        current_account_id.reset(token)
