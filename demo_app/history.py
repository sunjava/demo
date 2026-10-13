"""Account activity log and report helpers."""

from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from .models import AccountEvent, LineService, SapSalesOrder

CATEGORY_LABELS = {
    'PLAN': 'Plan',
    'PROTECTION': 'Protection',
    'SERVICE': 'Service',
    'TAX': 'Tax',
}

SNAPSHOT_STATUSES = [
    ('ACTIVE', 'Active'),
    ('PENDING_SHIPMENT', 'Ordered'),
    ('SHIPPED', 'Shipped'),
    ('SUSPENDED', 'Suspended'),
]


def _as_datetime(value):
    if value is None:
        return timezone.now()
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value)
        return value
    if isinstance(value, date):
        return timezone.make_aware(datetime.combine(value, time.min))
    return timezone.now()


def describe_line(line):
    if not line:
        return ''
    parts = [line.line_name]
    if line.msdn:
        parts.append(f'({line.msdn})')
    if line.employee_name:
        parts.append(f'for {line.employee_name}')
    return ' '.join(parts)


def record_event(
    account,
    event_type,
    summary,
    *,
    line=None,
    amount=None,
    reference='',
    occurred_at=None,
    dedupe=False,
):
    """Persist an account history event. Skip if dedupe and the same type+reference exists."""
    reference = reference or ''
    if dedupe and reference:
        if AccountEvent.objects.filter(
            account=account, event_type=event_type, reference=reference
        ).exists():
            return None
    amount_value = None if amount is None else Decimal(str(amount))
    return AccountEvent.objects.create(
        account=account,
        event_type=event_type,
        summary=summary,
        line=line,
        amount=amount_value,
        reference=reference,
        occurred_at=_as_datetime(occurred_at),
    )


def backfill_account_history(account):
    """Create missing history rows from current lines, SAP, services, and statements."""
    existing = set(account.events.values_list('event_type', 'reference'))

    def missing(event_type, reference):
        return (event_type, reference) not in existing

    for line in account.lines.all():
        reference = f'line:{line.id}'
        if missing('LINE_ADDED', reference):
            record_event(
                account,
                'LINE_ADDED',
                f'Line added: {describe_line(line)}',
                line=line,
                reference=reference,
                occurred_at=line.added_on,
                dedupe=True,
            )
            existing.add(('LINE_ADDED', reference))

    orders = SapSalesOrder.objects.filter(account=account).select_related('line', 'delivery')
    for order in orders:
        delivery = getattr(order, 'delivery', None)
        dispatched = order.status in ('DISPATCHED', 'IN_TRANSIT') or bool(
            delivery and delivery.dispatched
        )
        if not dispatched:
            continue
        if missing('DISPATCHED', order.sap_order_number):
            occurred = None
            if delivery:
                occurred = delivery.actual_dispatch_date or delivery.expected_dispatch_date
            record_event(
                account,
                'DISPATCHED',
                f'{describe_line(order.line)} dispatched ({order.sap_order_number})',
                line=order.line,
                reference=order.sap_order_number,
                occurred_at=occurred,
                dedupe=True,
            )
            existing.add(('DISPATCHED', order.sap_order_number))

    services = LineService.objects.filter(line__account=account).select_related('line', 'service')
    for line_service in services:
        reference = f'lineservice:{line_service.id}'
        if missing('SERVICE_ADDED', reference):
            record_event(
                account,
                'SERVICE_ADDED',
                f'{line_service.service.name} added to {describe_line(line_service.line)}',
                line=line_service.line,
                amount=line_service.total_amount,
                reference=reference,
                occurred_at=line_service.created_at or line_service.activated_at,
                dedupe=True,
            )
            existing.add(('SERVICE_ADDED', reference))

    for statement in account.billing_statements.all():
        statement_ref = f'statement:{statement.id}'
        period_label = statement.period_start.strftime('%b %Y')
        if missing('STATEMENT', statement_ref):
            record_event(
                account,
                'STATEMENT',
                f'Statement issued for {period_label}',
                amount=statement.total_amount,
                reference=statement_ref,
                occurred_at=statement.statement_date,
                dedupe=True,
            )
            existing.add(('STATEMENT', statement_ref))
        if statement.amount_paid > 0:
            payment_ref = f'payment:statement:{statement.id}'
            if missing('PAYMENT', payment_ref):
                occurred = account.last_payment_date if statement.status == 'PAID' else statement.statement_date
                record_event(
                    account,
                    'PAYMENT',
                    f'Payment of ${statement.amount_paid} for {period_label}',
                    amount=statement.amount_paid,
                    reference=payment_ref,
                    occurred_at=occurred,
                    dedupe=True,
                )
                existing.add(('PAYMENT', payment_ref))

    return account.events.count()


def _bar_pct(value, maximum):
    if not maximum:
        return 0
    return min(100, int((value / maximum) * 100))


def build_account_reports(account):
    """Summaries for the Reports tab from billing statements and lines."""
    statements = list(
        account.billing_statements.prefetch_related('line_items__line').all()[:6]
    )
    chronological = list(reversed(statements))
    max_total = max((row.total_amount for row in chronological), default=Decimal('0.00'))
    monthly = []
    for statement in chronological:
        monthly.append({
            'label': statement.period_start.strftime('%b %Y'),
            'total': statement.total_amount,
            'paid': statement.amount_paid,
            'billed_pct': _bar_pct(statement.total_amount, max_total),
            'paid_pct': _bar_pct(statement.amount_paid, max_total),
        })

    category_totals = defaultdict(lambda: Decimal('0.00'))
    line_totals = {}
    for statement in account.billing_statements.all():
        for item in statement.line_items.all():
            category_totals[item.category] += item.amount
            if not item.line_id:
                continue
            entry = line_totals.setdefault(item.line_id, {
                'line_name': item.line.line_name,
                'employee_name': item.line.employee_name or '—',
                'amount': Decimal('0.00'),
            })
            entry['amount'] += item.amount

    max_category = max(category_totals.values(), default=Decimal('0.00'))
    category_order = ['PLAN', 'PROTECTION', 'SERVICE', 'TAX']
    categories = []
    for key in category_order:
        if key not in category_totals:
            continue
        amount = category_totals[key]
        categories.append({
            'key': key,
            'label': CATEGORY_LABELS.get(key, key),
            'amount': amount,
            'pct': _bar_pct(amount, max_category),
        })
    for key, amount in category_totals.items():
        if key in category_order:
            continue
        categories.append({
            'key': key,
            'label': CATEGORY_LABELS.get(key, key),
            'amount': amount,
            'pct': _bar_pct(amount, max_category),
        })

    max_line = max((row['amount'] for row in line_totals.values()), default=Decimal('0.00'))
    by_line = sorted(line_totals.values(), key=lambda row: row['amount'], reverse=True)
    for row in by_line:
        row['pct'] = _bar_pct(row['amount'], max_line)

    status_counts = {
        row['status']: row['total']
        for row in account.lines.values('status').annotate(total=Count('id'))
    }
    snapshot = [
        {'key': key, 'label': label, 'count': status_counts.get(key, 0)}
        for key, label in SNAPSHOT_STATUSES
    ]

    return {
        'monthly': monthly,
        'categories': categories,
        'by_line': by_line,
        'snapshot': snapshot,
        'amount_due': account.amount_due,
        'due_immediately': account.due_immediately,
        'total_lines': account.lines.count(),
    }
