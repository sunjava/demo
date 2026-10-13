"""Mock SAP MCP server exposing order and dispatch tools over streamable HTTP."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'demo.settings')


def _ensure_django():
    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


_ensure_django()

from asgiref.sync import sync_to_async
from mcp.server.fastmcp import FastMCP

from demo_app.sap import (
    EXPECTED_DISPATCH_LINE_STATUSES,
    confirm_dispatch,
    find_orders,
)

_find_orders = sync_to_async(find_orders, thread_sensitive=True)
_confirm_dispatch = sync_to_async(confirm_dispatch, thread_sensitive=True)


def _find_expected(account_number: str, query: str = ''):
    return find_orders(account_number, query, EXPECTED_DISPATCH_LINE_STATUSES)


_find_expected_orders = sync_to_async(_find_expected, thread_sensitive=True)


def _unavailable(account_number: str, query: str) -> dict:
    return {
        'success': False,
        'error': 'No matching Shipment SAP order. The device is not marked dispatched; retry with an empty query if no person/MSDN was specified.',
        'account_number': account_number,
        'query': query,
        'orders': [],
    }


def create_mcp():
    from django.conf import settings

    mcp = FastMCP(
        'mock-sap',
        instructions='Mock SAP order and outbound-delivery system for device dispatch.',
        host=getattr(settings, 'SAP_MCP_HOST', '127.0.0.1'),
        port=int(getattr(settings, 'SAP_MCP_PORT', 3100)),
        streamable_http_path='/mcp',
        stateless_http=True,
    )

    @mcp.tool()
    async def sap_get_order(account_number: str, query: str = '') -> dict:
        """Look up open SAP sales orders (Shipment or Shipped only). Query may be employee name, MSDN, line name, device, or order number. Active lines are omitted."""
        orders = await _find_orders(account_number, query)
        if not orders:
            return _unavailable(account_number, query)
        return {'success': True, 'account_number': account_number, 'orders': orders}

    @mcp.tool()
    async def sap_get_dispatch_status(account_number: str, query: str = '') -> dict:
        """Return dispatch status for Shipment and Shipped lines only. Ignore Active lines."""
        orders = await _find_orders(account_number, query)
        if not orders:
            return _unavailable(account_number, query)
        results = []
        for order in orders:
            results.append({
                'sap_order_number': order['sap_order_number'],
                'employee_name': order['employee_name'],
                'msdn': order['msdn'],
                'device_model': order['device_model'],
                'line_status': order['line_status_display'],
                'dispatched': order['dispatched'],
                'status': order['status_display'],
                'actual_dispatch_date': order['actual_dispatch_date'],
                'tracking_number': order['tracking_number'],
                'carrier': order['carrier'],
            })
        return {'success': True, 'results': results}

    @mcp.tool()
    async def sap_get_expected_dispatch(account_number: str, query: str = '') -> dict:
        """Return expected dispatch date / ETA for Shipment lines only. Active lines have no dispatch expectation."""
        orders = await _find_expected_orders(account_number, query)
        if not orders:
            return _unavailable(account_number, query)
        results = []
        for order in orders:
            results.append({
                'sap_order_number': order['sap_order_number'],
                'employee_name': order['employee_name'],
                'msdn': order['msdn'],
                'device_model': order['device_model'],
                'line_status': order['line_status_display'],
                'dispatched': order['dispatched'],
                'expected_dispatch_date': order['expected_dispatch_date'],
                'actual_dispatch_date': order['actual_dispatch_date'],
                'delay_reason': order['delay_reason'] or None,
            })
        return {'success': True, 'results': results}

    @mcp.tool()
    async def sap_confirm_dispatch(account_number: str, query: str = '', carrier: str = 'UPS') -> dict:
        """Mark the SAP outbound delivery as dispatched. Matching Shipment lines become Shipped; they stay inactive until the customer activates."""
        result = await _confirm_dispatch(account_number, query, carrier)
        if not result.get('success'):
            return _unavailable(account_number, query)
        return result

    return mcp


def main():
    mcp = create_mcp()
    mcp.run(transport='streamable-http')


if __name__ == '__main__':
    main()
