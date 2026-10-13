from django.contrib.auth.models import User
from django.test import TestCase

from demo_app.agents.context import current_account_id
from demo_app.agents.billing_agent import (
    get_billing_summary,
    get_statement_line_items,
    preview_outstanding_payment,
)
from demo_app.agents.sap_agent import SAP_CUSTOMER_TOOL_NAMES, SAP_UNAVAILABLE, load_sap_tools, run_sap_agent
from demo_app.billing import generate_billing_statements, pay_outstanding_statements
from demo_app.history import backfill_account_history, build_account_reports
from demo_app.models import Account, Line, AccountEvent
from demo_app.sap import confirm_dispatch, confirm_dispatch_order, create_activation_order, find_orders, generate_sap_orders


class SapOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sapuser', password='x')
        self.account = Account.objects.create(
            account_number='SAP0001',
            user=self.user,
            status='ACTIVE',
        )
        self.line = Line.objects.create(
            account=self.account,
            line_name='Line 1',
            msdn='5551000001',
            employee_name='John Smith',
            employee_number='EMP001',
            status='PENDING_SHIPMENT',
            device_model='iPhone 15 Pro',
        )

    def test_generate_and_lookup_orders(self):
        result = generate_sap_orders()
        self.assertEqual(result['created'], 1)
        orders = find_orders(self.account.account_number, 'John')
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['employee_name'], 'John Smith')
        self.assertEqual(orders[0]['line_status'], 'PENDING_SHIPMENT')
        self.assertIn(orders[0]['status'], ['PENDING', 'IN_PACKING', 'IN_TRANSIT', 'DISPATCHED'])

    def test_find_orders_ignores_active_lines(self):
        generate_sap_orders()
        Line.objects.create(
            account=self.account,
            line_name='Line 2',
            msdn='5551000002',
            employee_name='Active Person',
            employee_number='EMP002',
            status='ACTIVE',
            device_model='iPhone 15 Pro',
        )
        generate_sap_orders()
        orders = find_orders(self.account.account_number)
        names = [order['employee_name'] for order in orders]
        self.assertEqual(names, ['John Smith'])
        self.assertFalse(any(order['line_status'] == 'ACTIVE' for order in orders))

    def test_generic_device_query_still_returns_pending_orders(self):
        generate_sap_orders()
        for query in ('device', 'Where is my device?', 'dispatch status', ''):
            orders = find_orders(self.account.account_number, query)
            self.assertEqual(len(orders), 1, query)
            self.assertEqual(orders[0]['employee_name'], 'John Smith')
            self.assertFalse(orders[0]['dispatched'])

    def test_sap_mcp_down_returns_unavailable(self):
        from django.test import override_settings

        with override_settings(SAP_MCP_URL='http://127.0.0.1:1/mcp'):
            tools = load_sap_tools()
            self.assertIsNone(tools)
            payload = run_sap_agent('Has John been dispatched?', self.account.id)
            self.assertTrue(payload.get('sap_unavailable'))
            self.assertIn('unavailable', payload['summary'].lower())
            self.assertEqual(payload['summary'], SAP_UNAVAILABLE)


class ActivationLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('actuser', password='x')
        self.account = Account.objects.create(
            account_number='ACT0001',
            user=self.user,
            status='ACTIVE',
        )
        self.existing = Line.objects.create(
            account=self.account,
            line_name='Line 1',
            msdn='5553000001',
            employee_name='Old Line',
            employee_number='EMP100',
            status='ACTIVE',
        )
        self.client.force_login(self.user)

    def test_new_activation_is_pending_and_first_in_list(self):
        older_added = self.existing.added_on
        import json
        response = self.client.post(
            '/api/lines/create/',
            data=json.dumps({
                'account_id': self.account.id,
                'device': {'model': 'iPhone 16', 'color': 'Black', 'storage': '256GB', 'price': 0},
                'plan': {'name': 'Magenta MAX', 'price': 85, 'dataLimit': 'Unlimited'},
                'protection': {'name': 'None', 'price': 0},
                'tradeIn': {'value': 0},
                'line': {'employeeName': 'New Hire', 'areaCode': '555'},
                'summary': {'totalMonthly': 85, 'dueNow': 0},
            }),
            content_type='application/json',
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['line']['status'], 'PENDING_SHIPMENT')

        lines = list(self.account.lines.order_by('-added_on', '-id'))
        self.assertEqual(lines[0].employee_name, 'New Hire')
        self.assertEqual(lines[0].status, 'PENDING_SHIPMENT')
        self.assertEqual(lines[1].id, self.existing.id)
        self.assertGreaterEqual(lines[0].added_on, older_added)

        page = self.client.get(f'/accounts/{self.account.id}/', HTTP_HOST='127.0.0.1')
        html = page.content.decode()
        pending_pos = html.find('New Hire')
        old_pos = html.find('Old Line')
        self.assertNotEqual(pending_pos, -1)
        self.assertNotEqual(old_pos, -1)
        self.assertLess(pending_pos, old_pos)
        self.assertIn('Shipment', html)
        self.assertEqual(lines[0].get_status_display(), 'Shipment')

        new_line = lines[0]
        self.assertFalse(new_line.activate_device())
        new_line.refresh_from_db()
        self.assertEqual(new_line.status, 'PENDING_SHIPMENT')

        dispatched = confirm_dispatch(self.account.account_number, 'New Hire')
        self.assertTrue(dispatched['success'])
        new_line.refresh_from_db()
        self.assertEqual(new_line.status, 'SHIPPED')
        self.assertEqual(new_line.get_status_display(), 'Shipped')

        import json
        activate = self.client.post(
            '/api/lines/activate/',
            data=json.dumps({'line_id': new_line.id}),
            content_type='application/json',
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(activate.status_code, 200, activate.content)
        new_line.refresh_from_db()
        self.assertEqual(new_line.status, 'ACTIVE')
        self.assertEqual(new_line.get_status_display(), 'Active')

    def test_create_activation_order_starts_pending(self):
        line = Line.objects.create(
            account=self.account,
            line_name='Line 2',
            msdn='5553000002',
            employee_name='Pending Person',
            employee_number='EMP101',
            status='PENDING_SHIPMENT',
            device_model='Galaxy S24',
        )
        order = create_activation_order(line)
        self.assertEqual(order.status, 'PENDING')
        self.assertFalse(order.delivery.dispatched)


class BillingSpecialistToolTests(TestCase):
    def setUp(self):
        from demo_app.billing import generate_billing_statements

        self.user = User.objects.create_user('billuser', password='x')
        self.account = Account.objects.create(
            account_number='BILL0001',
            user=self.user,
            status='ACTIVE',
        )
        Line.objects.create(
            account=self.account,
            line_name='Line 1',
            msdn='5552000001',
            employee_name='Jane Doe',
            employee_number='EMP002',
            status='ACTIVE',
            plan_name='T-Mobile Magenta MAX',
            plan_price=85,
            protection_name='Premium Device Protection',
            protection_price=18,
        )
        generate_billing_statements(Account.objects.filter(id=self.account.id), recreate=True)
        self.token = current_account_id.set(self.account.id)

    def tearDown(self):
        current_account_id.reset(self.token)

    def test_billing_summary_and_preview_are_read_only(self):
        summary = get_billing_summary.invoke({})
        self.assertGreater(summary['amount_due'], 0)
        before = self.account.amount_due
        preview = preview_outstanding_payment.invoke({})
        self.assertFalse(preview['executed'])
        self.assertEqual(preview['would_pay'], float(before))
        self.account.refresh_from_db()
        self.assertEqual(self.account.amount_due, before)

    def test_statement_line_items_include_charges(self):
        items = get_statement_line_items.invoke({})
        self.assertTrue(items['success'])
        descriptions = [row['description'] for row in items['line_items']]
        self.assertTrue(any('Magenta' in desc or 'Monthly' in desc for desc in descriptions))
        self.assertTrue(any(row['category'] == 'TAX' for row in items['line_items']))


class WarehouseDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('whuser', password='x')
        self.account = Account.objects.create(
            account_number='WH0001',
            user=self.user,
            status='ACTIVE',
        )
        self.line = Line.objects.create(
            account=self.account,
            line_name='Line 1',
            msdn='5554000001',
            employee_name='Vivek Vivek',
            employee_number='EMP6631',
            status='PENDING_SHIPMENT',
            device_model='iPhone 15 Pro',
        )
        self.order = create_activation_order(self.line)
        self.client.force_login(self.user)

    def test_warehouse_page_lists_pending_orders(self):
        page = self.client.get('/sap/warehouse/', HTTP_HOST='127.0.0.1')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn('SAP Warehouse', html)
        self.assertIn(self.order.sap_order_number, html)
        self.assertIn('Vivek Vivek', html)
        self.assertIn('Dispatch', html)

    def test_warehouse_dispatch_sets_line_shipped(self):
        import json
        response = self.client.post(
            '/api/sap/dispatch/',
            data=json.dumps({'sap_order_number': self.order.sap_order_number}),
            content_type='application/json',
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.line.refresh_from_db()
        self.assertEqual(self.line.status, 'SHIPPED')
        self.assertEqual(self.line.get_status_display(), 'Shipped')

    def test_customer_chat_cannot_use_confirm_dispatch_tool(self):
        self.assertNotIn('sap_confirm_dispatch', SAP_CUSTOMER_TOOL_NAMES)
        tools = load_sap_tools()
        if tools is not None:
            self.assertNotIn('sap_confirm_dispatch', [tool.name for tool in tools])


class AccountHistoryReportsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('histuser', password='x')
        self.account = Account.objects.create(
            account_number='HIST0001',
            user=self.user,
            status='ACTIVE',
        )
        self.line = Line.objects.create(
            account=self.account,
            line_name='Line 1',
            msdn='5555000001',
            employee_name='Vivek Vivek',
            employee_number='EMP6631',
            status='PENDING_SHIPMENT',
            device_model='iPhone 15 Pro',
            plan_name='T-Mobile Magenta MAX',
            plan_price=85,
            protection_name='Premium Device Protection',
            protection_price=18,
        )
        self.client.force_login(self.user)

    def test_lifecycle_events_and_reports(self):
        order = create_activation_order(self.line)
        result = confirm_dispatch_order(order.sap_order_number)
        self.assertTrue(result['success'])
        self.line.refresh_from_db()
        self.assertEqual(self.line.status, 'SHIPPED')
        self.assertTrue(self.line.activate_device())

        generate_billing_statements(Account.objects.filter(id=self.account.id), recreate=True)
        backfill_account_history(self.account)
        reports_before_pay = build_account_reports(self.account)
        self.assertGreater(reports_before_pay['amount_due'], 0)
        self.assertTrue(reports_before_pay['categories'])
        self.assertTrue(reports_before_pay['by_line'])

        pay_result = pay_outstanding_statements(self.account)
        self.assertTrue(pay_result['success'])
        self.assertGreater(pay_result['total_paid'], 0)

        types = list(
            AccountEvent.objects.filter(account=self.account)
            .order_by('occurred_at', 'id')
            .values_list('event_type', flat=True)
        )
        self.assertIn('LINE_ADDED', types)
        self.assertIn('DISPATCHED', types)
        self.assertIn('ACTIVATED', types)
        self.assertIn('PAYMENT', types)
        self.assertIn('STATEMENT', types)
        self.assertLess(types.index('LINE_ADDED'), types.index('DISPATCHED'))
        self.assertLess(types.index('DISPATCHED'), types.index('ACTIVATED'))

        page = self.client.get(f'/accounts/{self.account.id}/', HTTP_HOST='127.0.0.1')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn('Account History', html)
        self.assertIn('Dispatched', html)
        self.assertIn('Monthly billed vs paid', html)
        self.assertIn('Charges by category', html)
        self.assertIn('Charges by line', html)
        self.assertIn('Account snapshot', html)
        self.assertIn('Vivek Vivek', html)
