"""Mock SAP order/delivery lookups used by the MCP server."""

from datetime import date, timedelta

from django.db.models import Q

from .models import Line, SapDelivery, SapSalesOrder

STATUSES = ['DISPATCHED', 'IN_TRANSIT', 'IN_PACKING', 'PENDING']
CARRIERS = ['UPS', 'FedEx', 'USPS']
DISPATCH_LINE_STATUSES = ('PENDING_SHIPMENT', 'SHIPPED')
EXPECTED_DISPATCH_LINE_STATUSES = ('PENDING_SHIPMENT',)
GENERIC_QUERY_WORDS = {
    'a', 'an', 'the', 'my', 'mine', 'our', 'your', 'is', 'are', 'it', 'this',
    'that', 'where', 'when', 'will', 'would', 'likely', 'status', 'eta',
    'device', 'devices', 'phone', 'phones', 'order', 'orders', 'dispatch',
    'dispatched', 'shipment', 'ship', 'shipping', 'pending', 'please',
    'tell', 'me', 'about', 'for', 'on', 'to', 'of',
}


def _usable_query(query: str | None) -> str | None:
    """Drop generic phrases like 'my device' so account-wide pending orders are returned."""
    if not query or not str(query).strip():
        return None
    cleaned = ''.join(ch if ch.isalnum() or ch.isspace() else ' ' for ch in query)
    words = [word.lower() for word in cleaned.split() if word]
    if not words or all(word in GENERIC_QUERY_WORDS for word in words):
        return None
    return query.strip()


def _serialize_order(order: SapSalesOrder) -> dict:
    delivery = getattr(order, 'delivery', None)
    line = order.line
    return {
        'sap_order_number': order.sap_order_number,
        'account_number': order.account.account_number,
        'line_name': line.line_name,
        'msdn': line.msdn,
        'employee_name': line.employee_name,
        'employee_number': line.employee_number,
        'line_status': line.status,
        'line_status_display': line.get_status_display(),
        'device_model': order.device_model,
        'ordered_on': order.ordered_on.isoformat() if order.ordered_on else None,
        'status': order.status,
        'status_display': order.get_status_display(),
        'dispatched': bool(delivery.dispatched) if delivery else False,
        'actual_dispatch_date': (
            delivery.actual_dispatch_date.isoformat()
            if delivery and delivery.actual_dispatch_date else None
        ),
        'expected_dispatch_date': (
            delivery.expected_dispatch_date.isoformat()
            if delivery and delivery.expected_dispatch_date else None
        ),
        'carrier': delivery.carrier if delivery else '',
        'tracking_number': delivery.tracking_number if delivery else '',
        'delay_reason': delivery.delay_reason if delivery else '',
    }


def _order_queryset(account_number: str, query: str | None = None, line_statuses=DISPATCH_LINE_STATUSES):
    qs = SapSalesOrder.objects.filter(
        account__account_number=account_number
    ).select_related('line', 'account', 'delivery')
    if line_statuses:
        qs = qs.filter(line__status__in=line_statuses)
    q = _usable_query(query)
    if q:
        qs = qs.filter(
            Q(line__employee_name__icontains=q)
            | Q(line__msdn__icontains=q)
            | Q(line__line_name__icontains=q)
            | Q(line__employee_number__icontains=q)
            | Q(device_model__icontains=q)
            | Q(sap_order_number__icontains=q)
        )
    return qs


def find_orders(
    account_number: str,
    query: str | None = None,
    line_statuses=DISPATCH_LINE_STATUSES,
):
    return [
        _serialize_order(order)
        for order in _order_queryset(account_number, query, line_statuses)
    ]


def create_activation_order(line: Line) -> SapSalesOrder:
    """Create a pending SAP sales order for a newly placed activation."""
    order = SapSalesOrder.objects.create(
        account=line.account,
        line=line,
        sap_order_number=f'45{line.id:08d}',
        device_model=line.device_model or 'iPhone 15 Pro',
        ordered_on=date.today(),
        status='PENDING',
    )
    SapDelivery.objects.create(
        order=order,
        dispatched=False,
        expected_dispatch_date=date.today() + timedelta(days=3),
    )
    from .history import describe_line, record_event
    record_event(
        line.account,
        'LINE_ADDED',
        f'Line added: {describe_line(line)}',
        line=line,
        reference=f'line:{line.id}',
        occurred_at=line.added_on,
        dedupe=True,
    )
    return order


def _mark_dispatched(order: SapSalesOrder, carrier: str = 'UPS') -> SapSalesOrder:
    order.status = 'DISPATCHED'
    order.save(update_fields=['status'])
    delivery = getattr(order, 'delivery', None)
    if delivery:
        delivery.dispatched = True
        delivery.actual_dispatch_date = date.today()
        delivery.carrier = carrier or delivery.carrier or 'UPS'
        if not delivery.tracking_number:
            delivery.tracking_number = f'1Z{order.line_id:09d}'
        delivery.save()
    line = order.line
    if line.status == 'PENDING_SHIPMENT':
        line.status = 'SHIPPED'
        line.save(update_fields=['status'])
    from .history import describe_line, record_event
    record_event(
        order.account,
        'DISPATCHED',
        f'{describe_line(line)} dispatched ({order.sap_order_number})',
        line=line,
        reference=order.sap_order_number,
        dedupe=True,
    )
    return order


def confirm_dispatch(account_number: str, query: str | None = None, carrier: str = 'UPS') -> dict:
    """Record SAP dispatch. Pending-shipment lines become Shipped until the customer activates."""
    orders = list(_order_queryset(account_number, query, EXPECTED_DISPATCH_LINE_STATUSES))
    if not orders:
        return {
            'success': False,
            'error': 'No matching SAP sales order found',
            'account_number': account_number,
            'query': query or '',
            'results': [],
        }

    pending = [
        order for order in orders
        if not getattr(getattr(order, 'delivery', None), 'dispatched', False)
    ]
    targets = pending or orders
    results = []
    for order in targets:
        _mark_dispatched(order, carrier=carrier)
        order.refresh_from_db()
        order.line.refresh_from_db()
        payload = _serialize_order(order)
        payload['line_status'] = order.line.get_status_display()
        results.append(payload)
    return {'success': True, 'results': results}


def list_pending_dispatch_orders():
    return SapSalesOrder.objects.filter(
        line__status='PENDING_SHIPMENT',
    ).select_related('account', 'line', 'delivery').order_by('-ordered_on', '-id')


def confirm_dispatch_order(sap_order_number: str, carrier: str = 'UPS') -> dict:
    """Dispatch one SAP order by number. Used by the warehouse UI, not the customer chat."""
    order = SapSalesOrder.objects.select_related('line', 'account', 'delivery').filter(
        sap_order_number=sap_order_number,
    ).first()
    if not order:
        return {'success': False, 'error': 'SAP order not found'}
    if order.line.status != 'PENDING_SHIPMENT':
        return {
            'success': False,
            'error': (
                f'Only Ordered lines can be dispatched '
                f'(currently {order.line.get_status_display()}).'
            ),
        }
    _mark_dispatched(order, carrier=carrier)
    order.refresh_from_db()
    order.line.refresh_from_db()
    payload = _serialize_order(order)
    payload['line_status'] = order.line.get_status_display()
    return {'success': True, 'order': payload}


def generate_sap_orders(recreate: bool = False) -> dict:
    if recreate:
        SapDelivery.objects.all().delete()
        SapSalesOrder.objects.all().delete()

    created = 0
    skipped = 0
    lines = Line.objects.select_related('account').order_by('id')
    for index, line in enumerate(lines):
        if SapSalesOrder.objects.filter(line=line).exists():
            skipped += 1
            continue

        if line.status == 'PENDING_SHIPMENT':
            status = 'PENDING'
        elif line.status == 'SHIPPED':
            status = 'DISPATCHED'
        else:
            status = STATUSES[index % len(STATUSES)]
        ordered_on = date.today() - timedelta(days=8 + (index % 12))
        order = SapSalesOrder.objects.create(
            account=line.account,
            line=line,
            sap_order_number=f'45{line.id:08d}',
            device_model=line.device_model or 'iPhone 15 Pro',
            ordered_on=ordered_on,
            status=status,
        )

        dispatched = status in ('DISPATCHED', 'IN_TRANSIT')
        delay_reason = ''
        tracking = ''
        carrier = CARRIERS[index % len(CARRIERS)] if dispatched or status == 'IN_PACKING' else ''
        if status == 'DISPATCHED':
            actual = ordered_on + timedelta(days=3)
            expected = actual
            tracking = f'1Z{line.id:09d}'
        elif status == 'IN_TRANSIT':
            actual = date.today() - timedelta(days=1)
            expected = date.today() + timedelta(days=1)
            tracking = f'1Z{line.id:09d}'
        elif status == 'IN_PACKING':
            actual = None
            expected = date.today() + timedelta(days=2 + (index % 3))
        else:
            actual = None
            expected = date.today() + timedelta(days=7 + (index % 6))
            delay_reason = 'Warehouse backlog' if index % 2 == 0 else ''

        SapDelivery.objects.create(
            order=order,
            dispatched=dispatched,
            actual_dispatch_date=actual,
            expected_dispatch_date=expected,
            carrier=carrier,
            tracking_number=tracking,
            delay_reason=delay_reason,
        )
        created += 1

    return {'created': created, 'skipped': skipped, 'lines': lines.count()}
