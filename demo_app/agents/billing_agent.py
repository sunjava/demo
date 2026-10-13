"""Read-only Billing specialist used by the customer-facing supervisor."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from ..models import Account, BillingStatement
from .context import account_id

logger = logging.getLogger(__name__)

BILLING_PROMPT = """You are a billing specialist for this T-Mobile account.
You do not speak to the customer. Return a concise factual summary the front-desk agent can quote.

Cover amount due, due immediately (past-due only), statement totals, taxes, and line-item reasons for charges.
Do not greet. Do not take payment. If paying would help, say the unpaid total that would be collected if the customer asks to pay.
account_id is injected automatically.
"""


def _account() -> Account:
    return Account.objects.get(id=account_id())


def _serialize_statement(statement: BillingStatement) -> dict:
    return {
        'id': statement.id,
        'period_start': statement.period_start.isoformat(),
        'period_end': statement.period_end.isoformat(),
        'due_date': statement.due_date.isoformat(),
        'status': statement.status,
        'subtotal': float(statement.subtotal),
        'tax_amount': float(statement.tax_amount),
        'total_amount': float(statement.total_amount),
        'amount_paid': float(statement.amount_paid),
        'remaining_balance': float(statement.remaining_balance),
    }


@tool
def get_billing_summary() -> dict:
    """Account billing totals: amount due, due immediately, last payment, and unpaid statement count."""
    account = _account()
    unpaid = account.billing_statements.filter(status__in=['UNPAID', 'PAST_DUE'])
    return {
        'account_number': account.account_number,
        'amount_due': float(account.amount_due),
        'due_immediately': float(account.due_immediately),
        'last_payment_date': account.last_payment_date.isoformat() if account.last_payment_date else None,
        'payment_due_date': account.payment_due_date.isoformat() if account.payment_due_date else None,
        'unpaid_statement_count': unpaid.count(),
    }


@tool
def list_billing_statements(status_filter: Optional[str] = None) -> dict:
    """List billing statements. Optional status_filter: PAID, UNPAID, or PAST_DUE."""
    qs = _account().billing_statements.all()
    if status_filter:
        qs = qs.filter(status=status_filter.upper())
    statements = [_serialize_statement(statement) for statement in qs]
    return {'count': len(statements), 'statements': statements}


@tool
def get_statement_line_items(statement_id: Optional[int] = None) -> dict:
    """Line items for a statement (latest unpaid if statement_id is omitted). Use this to explain why a bill is high."""
    account = _account()
    if statement_id:
        statement = account.billing_statements.filter(id=statement_id).first()
    else:
        statement = (
            account.billing_statements.filter(status__in=['UNPAID', 'PAST_DUE'])
            .order_by('-period_start')
            .first()
            or account.billing_statements.order_by('-period_start').first()
        )
    if not statement:
        return {'success': False, 'error': 'No billing statement found'}

    items = [
        {
            'description': item.description,
            'category': item.category,
            'amount': float(item.amount),
            'line_name': item.line.line_name if item.line else None,
            'employee_name': item.line.employee_name if item.line else None,
        }
        for item in statement.line_items.all()
    ]
    payload = _serialize_statement(statement)
    payload['success'] = True
    payload['line_items'] = items
    return payload


@tool
def preview_outstanding_payment() -> dict:
    """Read-only preview of what would be paid if the customer confirmed Pay Now. Does not collect payment."""
    account = _account()
    unpaid = list(account.billing_statements.filter(status__in=['UNPAID', 'PAST_DUE']))
    statements = [_serialize_statement(statement) for statement in unpaid]
    return {
        'would_pay': float(account.amount_due),
        'due_immediately': float(account.due_immediately),
        'statements_that_would_be_paid': len(statements),
        'statements': statements,
        'executed': False,
        'note': 'Payment is not taken here. The front agent must use pay_account with Confirm.',
    }


BILLING_TOOLS = [
    get_billing_summary,
    list_billing_statements,
    get_statement_line_items,
    preview_outstanding_payment,
]


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


def run_billing_agent(question: str, account_id_value: int) -> Dict[str, Any]:
    from .context import current_account_id

    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key or api_key == 'your_openai_api_key_here':
        return {'success': False, 'error': 'OpenAI API key not configured', 'summary': ''}

    token = current_account_id.set(account_id_value)
    try:
        account = Account.objects.get(id=account_id_value)
        model = ChatOpenAI(model='gpt-4', temperature=0, api_key=api_key)
        agent = create_react_agent(model, BILLING_TOOLS, prompt=BILLING_PROMPT)
        result = agent.invoke(
            {
                'messages': [
                    HumanMessage(
                        content=(
                            f'Account {account.account_number}. '
                            f'Produce facts for: {question}'
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
        return {'success': True, 'summary': summary or 'No billing facts found.'}
    except Exception as exc:
        logger.exception('Billing specialist error')
        return {'success': False, 'error': str(exc), 'summary': f'Billing lookup failed: {exc}'}
    finally:
        current_account_id.reset(token)
