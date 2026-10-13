"""SAP specialist that calls the mock SAP MCP server for dispatch and ETA."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from ..models import Account
from .context import current_account_id

logger = logging.getLogger(__name__)

SAP_UNAVAILABLE = (
    'SAP order/dispatch system is currently unavailable. '
    'Could not retrieve dispatch or ETA information.'
)

SAP_PROMPT = """You are an SAP order-fulfillment specialist.
You do not speak to the customer. Return a concise factual summary the front-desk agent can quote.

Always pass the given account_number to every SAP tool.
If the question does not name a specific employee, MSDN, line, or order number, call tools with query='' (empty) so all Ordered lines on the account are returned. Do not put words like device, dispatch, shipment, or where into query.

Dispatch and ETA apply only to Ordered lines. A line is dispatched only when dispatched=true or line_status is Shipped.
Never say a device was already dispatched just because a tool returned no rows — that usually means the query was too specific. Retry with an empty query first.
Never report Active, Suspended, or Cancelled lines.
Use sap_get_expected_dispatch for ETA and sap_get_dispatch_status for dispatched vs not.
You cannot confirm warehouse dispatch. Never call sap_confirm_dispatch. Shipping is recorded only in the SAP warehouse UI.
Do not greet. Do not mention MCP.
"""


_loop = None


def _run_async(coro):
    """Run an awaitable on a long-lived loop (Django views are sync)."""
    global _loop
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
        return _loop.run_until_complete(coro)
    raise RuntimeError('SAP MCP client cannot run inside an existing event loop')


def _as_sync_tools(async_tools):
    from langchain_core.tools import StructuredTool

    wrapped = []
    for mcp_tool in async_tools:
        if getattr(mcp_tool, 'name', '') not in SAP_CUSTOMER_TOOL_NAMES:
            continue
        def _make_sync(tool):
            def _sync(**kwargs):
                return _run_async(tool.ainvoke(kwargs))

            return _sync

        wrapped.append(
            StructuredTool(
                name=mcp_tool.name,
                description=mcp_tool.description or mcp_tool.name,
                args_schema=mcp_tool.args_schema,
                func=_make_sync(mcp_tool),
                coroutine=mcp_tool.coroutine,
            )
        )
    return wrapped


async def _load_mcp_tools():
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            'sap': {
                'transport': 'streamable_http',
                'url': getattr(settings, 'SAP_MCP_URL', 'http://127.0.0.1:3100/mcp'),
                'timeout': 3.0,
            }
        }
    )
    return await client.get_tools()


SAP_CUSTOMER_TOOL_NAMES = frozenset({
    'sap_get_order',
    'sap_get_dispatch_status',
    'sap_get_expected_dispatch',
})


def load_sap_tools() -> Optional[list]:
    try:
        tools = _run_async(_load_mcp_tools())
        if tools is None:
            return None
        return [tool for tool in tools if getattr(tool, 'name', '') in SAP_CUSTOMER_TOOL_NAMES]
    except Exception as exc:
        logger.warning('Failed to load SAP MCP tools: %s', exc)
        return None


def _message_text(message: Any) -> str:
    content = getattr(message, 'content', '') or ''
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get('text'):
                parts.append(item['text'])
        return '\n'.join(parts)
    return str(content)


def run_sap_agent(question: str, account_id_value: int) -> Dict[str, Any]:
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key or api_key == 'your_openai_api_key_here':
        return {'success': False, 'error': 'OpenAI API key not configured', 'summary': ''}

    tools = load_sap_tools()
    if tools is None:
        return {
            'success': False,
            'sap_unavailable': True,
            'summary': SAP_UNAVAILABLE,
        }
    if not tools:
        return {
            'success': False,
            'sap_unavailable': True,
            'summary': SAP_UNAVAILABLE,
        }

    token = current_account_id.set(account_id_value)
    try:
        tools = _as_sync_tools(tools)
        account = Account.objects.get(id=account_id_value)
        model = ChatOpenAI(model='gpt-4', temperature=0, api_key=api_key)
        agent = create_react_agent(model, tools, prompt=SAP_PROMPT)
        result = agent.invoke(
            {
                'messages': [
                    HumanMessage(
                        content=(
                            f'account_number={account.account_number}. '
                            f'Look up dispatch/ETA for: {question}\n'
                            'If no person or MSDN is named, use query empty. '
                            'Do not conclude dispatched unless the tool says dispatched=true.'
                        )
                    )
                ]
            },
            {'recursion_limit': 12},
        )
        summary = ''
        messages: List[Any] = result.get('messages') if isinstance(result, dict) else []
        for message in messages:
            if isinstance(message, AIMessage):
                text = _message_text(message).strip()
                if text:
                    summary = text
        return {'success': True, 'summary': summary or 'No SAP order facts found.'}
    except Exception as exc:
        logger.exception('SAP specialist error')
        message = str(exc).lower()
        unavailable = any(
            token in message
            for token in ('connect', 'refused', 'timeout', 'unavailable', 'mcp')
        )
        return {
            'success': False,
            'sap_unavailable': unavailable,
            'error': str(exc),
            'summary': SAP_UNAVAILABLE if unavailable else f'SAP lookup failed: {exc}',
        }
    finally:
        current_account_id.reset(token)
