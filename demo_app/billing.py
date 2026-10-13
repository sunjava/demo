"""Helpers for generating monthly billing statements."""

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Prefetch

from .models import Account, BillingLineItem, BillingStatement, Line, LineService

TAX_RATE = Decimal('0.08')
DEFAULT_PLAN_NAME = 'T-Mobile Magenta MAX'
DEFAULT_PLAN_PRICE = Decimal('85.00')
DEFAULT_PROTECTION_NAME = 'Premium Device Protection'
DEFAULT_PROTECTION_PRICE = Decimal('18.00')
PAID_MONTHS = 5


def _add_months(year, month, delta):
    month_index = year * 12 + (month - 1) + delta
    return month_index // 12, month_index % 12 + 1


def _month_bounds(year, month):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return value


def _service_overlaps_period(line_service, period_start, period_end):
    activated = _as_date(line_service.activated_at) or _as_date(line_service.created_at)
    expires = _as_date(line_service.expires_at)

    if activated and activated > period_end:
        return False
    if expires and expires < period_start:
        return False
    return True


def _line_charge_items(line, period_start, period_end):
    items = []
    plan_price = line.plan_price or Decimal('0.00')
    protection_price = line.protection_price or Decimal('0.00')
    total_monthly = line.total_monthly_cost or Decimal('0.00')

    if plan_price > 0:
        plan_name = line.plan_name or DEFAULT_PLAN_NAME
        items.append({
            'line': line,
            'description': f'{plan_name} — {line.line_name} ({line.employee_name})',
            'category': 'PLAN',
            'amount': plan_price,
        })
    if protection_price > 0:
        protection_name = line.protection_name or DEFAULT_PROTECTION_NAME
        items.append({
            'line': line,
            'description': f'{protection_name} — {line.line_name} ({line.employee_name})',
            'category': 'PROTECTION',
            'amount': protection_price,
        })

    if not items:
        if total_monthly > 0:
            items.append({
                'line': line,
                'description': f'Monthly service — {line.line_name} ({line.employee_name})',
                'category': 'PLAN',
                'amount': total_monthly,
            })
        else:
            items.append({
                'line': line,
                'description': f'{DEFAULT_PLAN_NAME} — {line.line_name} ({line.employee_name})',
                'category': 'PLAN',
                'amount': DEFAULT_PLAN_PRICE,
            })
            items.append({
                'line': line,
                'description': f'{DEFAULT_PROTECTION_NAME} — {line.line_name} ({line.employee_name})',
                'category': 'PROTECTION',
                'amount': DEFAULT_PROTECTION_PRICE,
            })

    for line_service in line.line_services.all():
        if not _service_overlaps_period(line_service, period_start, period_end):
            continue
        service_amount = line_service.amount_paid or Decimal('0.00')
        if service_amount <= 0:
            continue
        service_name = line_service.service.name if line_service.service_id else 'Add-on service'
        items.append({
            'line': line,
            'description': f'{service_name} — {line.line_name} ({line.employee_name})',
            'category': 'SERVICE',
            'amount': service_amount,
        })

    return items


def _billable_lines(account):
    return [
        line for line in account.lines.all()
        if line.status in ('ACTIVE', 'SUSPENDED')
    ]


def _sync_account_dates(account):
    current_start, _ = _month_bounds(date.today().year, date.today().month)
    current = account.billing_statements.filter(period_start=current_start).first()
    latest_paid = account.billing_statements.filter(status='PAID').order_by('-due_date').first()

    update_fields = []
    if current:
        account.payment_due_date = current.due_date
        update_fields.append('payment_due_date')
    if latest_paid:
        paid_on = latest_paid.due_date - timedelta(days=5)
        if paid_on < latest_paid.period_start:
            paid_on = latest_paid.statement_date
        account.last_payment_date = paid_on
        update_fields.append('last_payment_date')
    if update_fields:
        account.save(update_fields=update_fields)


def generate_statement_for_period(account, period_start, period_end, status, recreate=False):
    existing = BillingStatement.objects.filter(account=account, period_start=period_start).first()
    if existing and not recreate:
        existing.refresh_status()
        return existing, False

    if existing and recreate:
        existing.delete()

    items = []
    for line in _billable_lines(account):
        items.extend(_line_charge_items(line, period_start, period_end))

    subtotal = sum((item['amount'] for item in items), Decimal('0.00'))
    tax_amount = (subtotal * TAX_RATE).quantize(Decimal('0.01'))
    total_amount = subtotal + tax_amount

    if status == 'PAST_DUE' and total_amount <= 0:
        status = 'UNPAID'

    amount_paid = total_amount if status == 'PAID' else Decimal('0.00')

    statement = BillingStatement.objects.create(
        account=account,
        period_start=period_start,
        period_end=period_end,
        statement_date=period_end,
        due_date=period_end,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        amount_paid=amount_paid,
        status=status,
    )

    for item in items:
        BillingLineItem.objects.create(
            statement=statement,
            line=item['line'],
            description=item['description'],
            category=item['category'],
            amount=item['amount'],
        )

    if tax_amount > 0:
        BillingLineItem.objects.create(
            statement=statement,
            line=None,
            description='Taxes & fees (8%)',
            category='TAX',
            amount=tax_amount,
        )

    statement.refresh_status()
    return statement, True


def generate_billing_statements(accounts=None, months_back=PAID_MONTHS, recreate=False):
    """
    Generate monthly statements for the given accounts (or all accounts).

    Creates `months_back` prior paid months plus the current month as UNPAID
    (or PAST_DUE if the due date has already passed).
    """
    today = date.today()
    if accounts is None:
        accounts = Account.objects.all()

    accounts = accounts.prefetch_related(
        Prefetch(
            'lines',
            queryset=Line.objects.prefetch_related(
                Prefetch('line_services', queryset=LineService.objects.select_related('service'))
            ),
        ),
        'billing_statements',
    )

    created_count = 0
    skipped_count = 0

    for account in accounts:
        for offset in range(months_back, -1, -1):
            year, month = _add_months(today.year, today.month, -offset)
            period_start, period_end = _month_bounds(year, month)
            is_current = offset == 0

            if is_current:
                status = 'PAST_DUE' if period_end < today else 'UNPAID'
            else:
                status = 'PAID'

            _, created = generate_statement_for_period(
                account,
                period_start,
                period_end,
                status,
                recreate=recreate,
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        _sync_account_dates(account)

    return {
        'created': created_count,
        'skipped': skipped_count,
        'accounts': accounts.count() if hasattr(accounts, 'count') else len(list(accounts)),
    }


def pay_outstanding_statements(account):
    """Pay all unpaid and past-due statements on an account."""
    unpaid_statements = list(
        account.billing_statements.filter(status__in=['UNPAID', 'PAST_DUE'])
    )
    if not unpaid_statements:
        return {
            'success': True,
            'message': 'No balance due',
            'amount_due': 0.0,
            'due_immediately': 0.0,
            'last_payment_date': account.last_payment_date.isoformat() if account.last_payment_date else None,
            'statements_paid': 0,
            'total_paid': 0.0,
        }

    payment_date = date.today()
    total_paid = Decimal('0.00')
    from .history import record_event
    for statement in unpaid_statements:
        remaining = statement.remaining_balance
        total_paid += remaining
        statement.mark_paid(payment_date)
        period_label = statement.period_start.strftime('%b %Y')
        record_event(
            account,
            'PAYMENT',
            f'Payment of ${remaining} for {period_label}',
            amount=remaining,
            reference=f'payment:statement:{statement.id}',
            occurred_at=payment_date,
            dedupe=True,
        )

    account.last_payment_date = payment_date
    account.save(update_fields=['last_payment_date'])
    return {
        'success': True,
        'message': f'{len(unpaid_statements)} statement(s) paid successfully',
        'amount_due': float(account.amount_due),
        'due_immediately': float(account.due_immediately),
        'last_payment_date': account.last_payment_date.isoformat(),
        'statements_paid': len(unpaid_statements),
        'total_paid': float(total_paid),
    }
