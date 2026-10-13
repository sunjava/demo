from contextvars import ContextVar
from typing import Optional

current_account_id: ContextVar[Optional[int]] = ContextVar("account_id", default=None)


def account_id() -> int:
    value = current_account_id.get()
    if not value:
        raise ValueError("Account ID is not set for this chatbot turn")
    return value
