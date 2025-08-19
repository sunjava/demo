from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json
import uuid
from datetime import timedelta

from .models import Account, Line, Service, LineService
from .chatbot import chatbot

# Create your views here.

@login_required
def hello_world(request):
    """Dashboard view with real account data"""
    # Get recently viewed accounts from session
    recently_viewed_data = request.session.get('recently_viewed_accounts', {})
    
    # Get recently viewed accounts (limit to 3)
    if recently_viewed_data:
        # Sort by timestamp (most recent first) and get the first 3
        sorted_accounts = sorted(recently_viewed_data.items(), key=lambda x: x[1], reverse=True)
        recent_accounts = []
        for account_id_str, timestamp in sorted_accounts[:3]:
            try:
                account_id = int(account_id_str)
                account = Account.objects.get(id=account_id)
                # Add the last viewed timestamp to the account object
                from django.utils import timezone
                from datetime import datetime
                account.last_viewed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                recent_accounts.append(account)
            except (Account.DoesNotExist, ValueError):
                # Remove invalid account IDs from session
                del recently_viewed_data[account_id_str]
                request.session['recently_viewed_accounts'] = recently_viewed_data
    else:
        # Fallback to recently modified accounts if no recently viewed
        recent_accounts = Account.objects.all().order_by('-last_modified_on')[:3]
    
    # Get account statistics
    total_accounts = Account.objects.count()
    total_lines = Line.objects.count()
    active_lines = Line.objects.filter(status='ACTIVE').count()
    suspended_lines = Line.objects.filter(status='SUSPENDED').count()
    cancelled_lines = Line.objects.filter(status='CANCELLED').count()
    
    context = {
        'recent_accounts': recent_accounts,
        'total_accounts': total_accounts,
        'total_lines': total_lines,
        'active_lines': active_lines,
        'suspended_lines': suspended_lines,
        'cancelled_lines': cancelled_lines,
    }
    return render(request, 'dashboard.html', context)

@login_required
def all_accounts(request):
    """Display all accounts in a list format"""
    accounts = Account.objects.all().order_by('-last_modified_on')
    
    # Get statistics for each account
    for account in accounts:
        account.total_lines = account.lines.count()
        account.active_lines = account.lines.filter(status='ACTIVE').count()
        account.suspended_lines = account.lines.filter(status='SUSPENDED').count()
        account.cancelled_lines = account.lines.filter(status='CANCELLED').count()
    
    context = {
        'accounts': accounts,
        'total_accounts': accounts.count(),
    }
    return render(request, 'demo_app/all_accounts.html', context)

@login_required
def all_lines(request):
    """Display all lines across all accounts grouped by account and sorted by created date"""
    # Get accounts with their lines, ordered by account last modified date (newest first)
    accounts_with_lines = Account.objects.prefetch_related(
        'lines'
    ).order_by('-last_modified_on')
    
    # Get statistics
    total_lines = Line.objects.count()
    active_lines = Line.objects.filter(status='ACTIVE').count()
    suspended_lines = Line.objects.filter(status='SUSPENDED').count()
    cancelled_lines = Line.objects.filter(status='CANCELLED').count()
    
    # Get unique accounts for the filter dropdown
    unique_accounts = Account.objects.values_list('account_number', flat=True).distinct().order_by('account_number')
    
    # Get status filter from URL parameter
    status_filter = request.GET.get('status', '')
    
    # Calculate filtered line count based on status
    if status_filter == 'ACTIVE':
        filtered_count = active_lines
        page_title = f"All Active Lines ({filtered_count})"
    elif status_filter == 'SUSPENDED':
        filtered_count = suspended_lines
        page_title = f"All Suspended Lines ({filtered_count})"
    elif status_filter == 'CANCELLED':
        filtered_count = cancelled_lines
        page_title = f"All Cancelled Lines ({filtered_count})"
    else:
        filtered_count = total_lines
        page_title = f"All Lines by Account ({filtered_count})"
    
    context = {
        'accounts_with_lines': accounts_with_lines,
        'total_lines': total_lines,
        'active_lines': active_lines,
        'suspended_lines': suspended_lines,
        'cancelled_lines': cancelled_lines,
        'unique_accounts': unique_accounts,
        'status_filter': status_filter,
        'page_title': page_title,
        'filtered_count': filtered_count,
    }
    return render(request, 'demo_app/all_lines.html', context)

@login_required
def account_details(request, account_id):
    """Display account details with lines loaded from database"""
    account = get_object_or_404(Account, id=account_id)
    lines = account.lines.all().order_by('line_name')
    
    # Track recently viewed accounts in session with timestamps
    recently_viewed_data = request.session.get('recently_viewed_accounts', {})
    
    # Add current timestamp for this account
    from django.utils import timezone
    current_time = timezone.now().isoformat()
    recently_viewed_data[str(account_id)] = current_time
    
    # Keep only the last 10 recently viewed accounts
    if len(recently_viewed_data) > 10:
        # Sort by timestamp and keep only the 10 most recent
        sorted_accounts = sorted(recently_viewed_data.items(), key=lambda x: x[1], reverse=True)
        recently_viewed_data = dict(sorted_accounts[:10])
    
    # Save back to session
    request.session['recently_viewed_accounts'] = recently_viewed_data
    
    context = {
        'account': account,
        'lines': lines,
        'account_id': account_id
    }
    return render(request, 'demo_app/account_details.html', context)

@login_required
def line_details(request, account_id, line_id):
    """Display line details with services"""
    account = get_object_or_404(Account, id=account_id)
    line = get_object_or_404(Line, id=line_id, account=account)
    
    # Get services for this line
    line_services = LineService.objects.filter(line=line).select_related('service').order_by('-activated_at')
    
    context = {
        'account': account,
        'line': line,
        'line_services': line_services,
    }
    return render(request, 'demo_app/line_details.html', context)

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        # Enhanced debug logging
        print(f"DEBUG: Request method: {request.method}")
        print(f"DEBUG: Request content type: {request.content_type}")
        print(f"DEBUG: Request encoding: {request.encoding}")
        print(f"DEBUG: POST data type: {type(request.POST)}")
        print(f"DEBUG: POST data keys: {list(request.POST.keys())}")
        print(f"DEBUG: Raw POST data: {request.POST}")
        print(f"DEBUG: request.body: {request.body}")
        
        # Try different ways to get the data
        username_post = request.POST.get('username')
        password_post = request.POST.get('password')
        
        print(f"DEBUG: username from POST.get('username'): '{username_post}'")
        print(f"DEBUG: password from POST.get('password'): '{password_post}'")
        
        # Try alternative methods
        if hasattr(request, 'data'):
            print(f"DEBUG: request.data: {request.data}")
        
        # Check if data is in request.POST or request.body
        if username_post and password_post:
            username = username_post
            password = password_post
            print(f"DEBUG: Using POST data - Username: '{username}', Password: '{password}'")
        else:
            # Try to parse from body if POST is empty
            print(f"DEBUG: POST data is empty, checking request.body")
            try:
                import json
                body_data = json.loads(request.body)
                username = body_data.get('username')
                password = body_data.get('password')
                print(f"DEBUG: Parsed from body - Username: '{username}', Password: '{password}'")
            except:
                print(f"DEBUG: Could not parse body as JSON")
                username = username_post or ''
                password = password_post or ''
        
        print(f"DEBUG: Final values - Username: '{username}', Password: '{password}'")
        print(f"DEBUG: Username length: {len(username) if username else 0}")
        print(f"DEBUG: Password length: {len(password) if password else 0}")
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            print(f"DEBUG: Authentication successful for user: {user.username}")
            login(request, user)
            return redirect('dashboard')
        else:
            print(f"DEBUG: Authentication failed for username: '{username}'")
            return render(request, 'demo_app/login.html', {'error': 'Invalid username or password'})
    return render(request, 'demo_app/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 != password2:
            return render(request, 'demo_app/signup.html', {'error': 'Passwords do not match'})
        if User.objects.filter(username=username).exists():
            return render(request, 'demo_app/signup.html', {'error': 'Username already exists'})
        user = User.objects.create_user(username=username, password=password1)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'demo_app/signup.html')


# API Views for Service Management

@login_required
@require_http_methods(["GET"])
def get_services(request):
    """Get all available services"""
    services = Service.objects.filter(is_active=True)
    services_data = []
    
    for service in services:
        services_data.append({
            'id': service.id,
            'name': service.name,
            'service_type': service.service_type,
            'description': service.description,
            'price': float(service.price),
            'duration_days': service.duration_days,
            'data_allowance_mb': service.data_allowance_mb,
            'features': service.features
        })
    
    return JsonResponse({'services': services_data})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def add_service_to_lines(request):
    """Add a service to selected lines"""
    try:
        data = json.loads(request.body)
        service_id = data.get('service_id')
        line_ids = data.get('line_ids', [])
        payment_method = data.get('payment_method', 'Credit Card')
        
        if not service_id or not line_ids:
            return JsonResponse({'error': 'Service ID and Line IDs are required'}, status=400)
        
        service = get_object_or_404(Service, id=service_id)
        lines = Line.objects.filter(id__in=line_ids)
        
        if not lines.exists():
            return JsonResponse({'error': 'No valid lines found'}, status=400)
        
        # Calculate pricing
        base_price = service.price
        tax_rate = Decimal('0.08')  # 8% tax
        tax_amount = base_price * tax_rate
        total_amount = base_price + tax_amount
        
        created_services = []
        
        # Create LineService records for each selected line
        for line in lines:
            # Check if line already has this service active
            existing_service = LineService.objects.filter(
                line=line,
                service=service,
                status__in=['PENDING', 'ACTIVE']
            ).exists()
            
            if existing_service:
                continue  # Skip if service already exists
            
            # Calculate expiration date
            expires_at = timezone.now() + timedelta(days=service.duration_days)
            
            line_service = LineService.objects.create(
                line=line,
                service=service,
                status='ACTIVE',  # Immediately activate for demo
                activated_at=timezone.now(),
                expires_at=expires_at,
                amount_paid=base_price,
                tax_amount=tax_amount,
                total_amount=total_amount,
                payment_method=payment_method,
                transaction_id=str(uuid.uuid4())[:8].upper()
            )
            
            created_services.append({
                'line_service_id': line_service.id,
                'line_name': line.line_name,
                'msdn': line.msdn,
                'service_name': service.name,
                'status': line_service.status,
                'activated_at': line_service.activated_at.isoformat(),
                'expires_at': line_service.expires_at.isoformat(),
                'total_amount': float(line_service.total_amount)
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Service "{service.name}" added to {len(created_services)} line(s)',
            'services_added': created_services,
            'service_details': {
                'name': service.name,
                'price': float(base_price),
                'tax_amount': float(tax_amount),
                'total_amount': float(total_amount)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_line_services(request, line_id):
    """Get all services for a specific line"""
    line = get_object_or_404(Line, id=line_id)
    line_services = LineService.objects.filter(line=line).select_related('service')
    
    services_data = []
    for line_service in line_services:
        services_data.append({
            'id': line_service.id,
            'service_name': line_service.service.name,
            'status': line_service.status,
            'activated_at': line_service.activated_at.isoformat() if line_service.activated_at else None,
            'expires_at': line_service.expires_at.isoformat() if line_service.expires_at else None,
            'total_amount': float(line_service.total_amount),
            'transaction_id': line_service.transaction_id
        })
    
    return JsonResponse({
        'line': {
            'id': line.id,
            'name': line.line_name,
            'msdn': line.msdn
        },
        'services': services_data
    })


@login_required
@require_http_methods(["GET"])
def get_account_lines(request, account_id):
    """Get all lines for an account with their current services"""
    account = get_object_or_404(Account, id=account_id)
    lines = account.lines.all()
    
    lines_data = []
    for line in lines:
        active_services = LineService.objects.filter(
            line=line,
            status__in=['PENDING', 'ACTIVE']
        ).select_related('service')
        
        services_data = []
        for line_service in active_services:
            services_data.append({
                'service_name': line_service.service.name,
                'status': line_service.status,
                'expires_at': line_service.expires_at.isoformat() if line_service.expires_at else None
            })
        
        lines_data.append({
            'id': line.id,
            'line_name': line.line_name,
            'msdn': line.msdn,
            'employee_name': line.employee_name,
            'employee_number': line.employee_number,
            'status': line.status,
            'added_on': line.added_on.isoformat(),
            'payment_due_date': line.payment_due_date.isoformat() if line.payment_due_date else None,
            'active_services': services_data
        })
    
    return JsonResponse({
        'account': {
            'id': account.id,
            'account_number': account.account_number,
            'status': account.status
        },
        'lines': lines_data
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def suspend_lines(request):
    """Suspend selected lines"""
    try:
        data = json.loads(request.body)
        line_ids = data.get('line_ids', [])
        
        if not line_ids:
            return JsonResponse({'error': 'Line IDs are required'}, status=400)
        
        lines = Line.objects.filter(id__in=line_ids)
        
        if not lines.exists():
            return JsonResponse({'error': 'No valid lines found'}, status=400)
        
        suspended_lines = []
        
        for line in lines:
            if line.status == 'ACTIVE':
                line.status = 'SUSPENDED'
                line.save()
                suspended_lines.append({
                    'line_id': line.id,
                    'line_name': line.line_name,
                    'msdn': line.msdn,
                    'status': line.status
                })
        
        return JsonResponse({
            'success': True,
            'message': f'{len(suspended_lines)} line(s) suspended successfully',
            'suspended_lines': suspended_lines
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def restore_lines(request):
    """Restore selected lines"""
    try:
        data = json.loads(request.body)
        line_ids = data.get('line_ids', [])
        
        if not line_ids:
            return JsonResponse({'error': 'Line IDs are required'}, status=400)
        
        lines = Line.objects.filter(id__in=line_ids)
        
        if not lines.exists():
            return JsonResponse({'error': 'No valid lines found'}, status=400)
        
        restored_lines = []
        
        for line in lines:
            if line.status == 'SUSPENDED':
                line.status = 'ACTIVE'
                line.save()
                restored_lines.append({
                    'line_id': line.id,
                    'line_name': line.line_name,
                    'msdn': line.msdn,
                    'status': line.status
                })
        
        return JsonResponse({
            'success': True,
            'message': f'{len(restored_lines)} line(s) restored successfully',
            'restored_lines': restored_lines
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_line(request):
    """Create a new line with device, plan, and other options"""
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')
        device_data = data.get('device', {})
        plan_data = data.get('plan', {})
        protection_data = data.get('protection', {})
        trade_in_data = data.get('tradeIn', {})
        line_data = data.get('line', {})
        summary_data = data.get('summary', {})
        
        if not account_id:
            return JsonResponse({'error': 'Account ID is required'}, status=400)
        
        # Validate account exists
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return JsonResponse({'error': 'Account not found'}, status=404)
        
        # Generate a unique MSDN (phone number)
        import random
        area_code = line_data.get('areaCode', '555')
        # Generate a random 7-digit number
        phone_number = f"{random.randint(1000000, 9999999)}"
        msdn = f"+1-{area_code}-{phone_number[:3]}-{phone_number[3:]}"
        
        # Generate employee number
        employee_number = f"EMP{random.randint(1000, 9999)}"
        
        # Calculate payment due date (last day of current month)
        from datetime import date
        import calendar
        today = date.today()
        last_day_of_month = calendar.monthrange(today.year, today.month)[1]
        payment_due_date = date(today.year, today.month, last_day_of_month)
        
        # Create the line with device, plan, and protection information
        line = Line.objects.create(
            account=account,
            line_name=f"Line {account.lines.count() + 1}",
            msdn=msdn,
            employee_name=line_data.get('employeeName', 'Unknown Employee'),
            employee_number=employee_number,
            status='ACTIVE',
            payment_due_date=payment_due_date,
            
            # Device information
            device_model=device_data.get('model', 'Unknown Device'),
            device_color=device_data.get('color', 'Unknown Color'),
            device_storage=device_data.get('storage', 'Unknown Storage'),
            device_price=device_data.get('price', 0),
            
            # Plan information
            plan_name=plan_data.get('name', 'Unknown Plan'),
            plan_price=plan_data.get('price', 0),
            plan_data_limit=plan_data.get('dataLimit', 'Unlimited'),
            
            # Protection information
            protection_name=protection_data.get('name', 'No Protection'),
            protection_price=protection_data.get('price', 0),
            
            # Trade-in and total information
            trade_in_value=trade_in_data.get('value', 0),
            total_monthly_cost=summary_data.get('totalMonthly', 0)
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Line created successfully',
            'line': {
                'id': line.id,
                'line_name': line.line_name,
                'msdn': line.msdn,
                'employee_name': line.employee_name,
                'employee_number': line.employee_number,
                'status': line.status,
                'device_details': f"{line.device_model} - {line.device_color}, {line.device_storage}",
                'plan_name': line.plan_name,
                'plan_price': float(line.plan_price) if line.plan_price else 0,
                'protection_name': line.protection_name,
                'protection_price': float(line.protection_price) if line.protection_price else 0,
                'trade_in_value': float(line.trade_in_value) if line.trade_in_value else 0,
                'total_monthly': float(line.total_monthly_cost) if line.total_monthly_cost else 0,
                'due_now': summary_data.get('dueNow', 0)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def get_line_details(request, line_id):
    """Get detailed information about a specific line including device, plan, and protection"""
    try:
        line = get_object_or_404(Line, id=line_id)
        
        return JsonResponse({
            'success': True,
            'line': {
                'id': line.id,
                'line_name': line.line_name,
                'msdn': line.msdn,
                'employee_name': line.employee_name,
                'employee_number': line.employee_number,
                'status': line.status,
                'device_model': line.device_model,
                'device_color': line.device_color,
                'device_storage': line.device_storage,
                'device_price': float(line.device_price) if line.device_price else None,
                'plan_name': line.plan_name,
                'plan_price': float(line.plan_price) if line.plan_price else None,
                'plan_data_limit': line.plan_data_limit,
                'protection_name': line.protection_name,
                'protection_price': float(line.protection_price) if line.protection_price else None,
                'trade_in_value': float(line.trade_in_value) if line.trade_in_value else None,
                'total_monthly_cost': float(line.total_monthly_cost) if line.total_monthly_cost else None
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_mirrored_line(request):
    """Create a new line by mirroring an existing line"""
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')
        line_to_mirror_id = data.get('line_to_mirror_id')
        new_employee_name = data.get('new_employee_name')
        new_line_name = data.get('new_line_name')
        
        if not account_id or not line_to_mirror_id or not new_employee_name:
            return JsonResponse({'error': 'Account ID, line to mirror ID, and new employee name are required'}, status=400)
        
        # Validate account exists
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return JsonResponse({'error': 'Account not found'}, status=404)
        
        # Validate line to mirror exists
        try:
            line_to_mirror = Line.objects.get(id=line_to_mirror_id, account=account)
        except Line.DoesNotExist:
            return JsonResponse({'error': 'Line to mirror not found'}, status=404)
        
        # Generate a unique MSDN (phone number)
        import random
        area_code = '555'  # Default area code
        # Generate a random 7-digit number
        phone_number = f"{random.randint(1000000, 9999999)}"
        msdn = f"+1-{area_code}-{phone_number[:3]}-{phone_number[3:]}"
        
        # Generate employee number
        employee_number = f"EMP{random.randint(1000, 9999)}"
        
        # Calculate payment due date (last day of current month)
        from datetime import date
        import calendar
        today = date.today()
        last_day_of_month = calendar.monthrange(today.year, today.month)[1]
        payment_due_date = date(today.year, today.month, last_day_of_month)
        
        # Generate a proper line number (Line X) instead of using "Mirrored Line"
        if not new_line_name or new_line_name.lower() == 'mirrored line':
            # Count existing lines to get the next line number
            existing_line_count = account.lines.count()
            new_line_name = f"Line {existing_line_count + 1}"
        
        # Create the new line with same settings as the mirrored line
        line = Line.objects.create(
            account=account,
            line_name=new_line_name,
            msdn=msdn,
            employee_name=new_employee_name,
            employee_number=employee_number,
            status='ACTIVE',
            payment_due_date=payment_due_date,
            
            # Copy device information from mirrored line
            device_model=line_to_mirror.device_model,
            device_color=line_to_mirror.device_color,
            device_storage=line_to_mirror.device_storage,
            device_price=line_to_mirror.device_price,
            
            # Copy plan information from mirrored line
            plan_name=line_to_mirror.plan_name,
            plan_price=line_to_mirror.plan_price,
            plan_data_limit=line_to_mirror.plan_data_limit,
            
            # Copy protection information from mirrored line
            protection_name=line_to_mirror.protection_name,
            protection_price=line_to_mirror.protection_price,
            
            # Copy trade-in and total information from mirrored line
            trade_in_value=line_to_mirror.trade_in_value,
            total_monthly_cost=line_to_mirror.total_monthly_cost
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Mirrored line created successfully',
            'line': {
                'id': line.id,
                'line_name': line.line_name,
                'msdn': line.msdn,
                'employee_name': line.employee_name,
                'employee_number': line.employee_number,
                'status': line.status,
                'device_details': f"{line.device_model} - {line.device_color}, {line.device_storage}" if line.device_model else "Not specified",
                'plan_name': line.plan_name or "Not specified",
                'protection_name': line.protection_name or "Not specified",
                'mirrored_from': {
                    'id': line_to_mirror.id,
                    'line_name': line_to_mirror.line_name,
                    'employee_name': line_to_mirror.employee_name
                }
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_account_status(request):
    """Update account status and handle line status changes"""
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')
        new_status = data.get('status')
        
        if not account_id or not new_status:
            return JsonResponse({'error': 'Account ID and status are required'}, status=400)
        
        if new_status not in ['ACTIVE', 'INACTIVE']:
            return JsonResponse({'error': 'Invalid status. Must be ACTIVE or INACTIVE'}, status=400)
        
        # Validate account exists
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return JsonResponse({'error': 'Account not found'}, status=404)
        
        old_status = account.status
        
        # Update account status using the model method
        account.update_status(new_status)
        
        # Get updated line counts
        total_lines = account.lines.count()
        active_lines = account.lines.filter(status='ACTIVE').count()
        suspended_lines = account.lines.filter(status='SUSPENDED').count()
        inactive_lines = account.lines.filter(status='INACTIVE').count()
        
        return JsonResponse({
            'success': True,
            'message': f'Account status updated from {old_status} to {new_status}',
            'account': {
                'id': account.id,
                'account_number': account.account_number,
                'status': account.status,
                'account_type': account.account_type
            },
            'line_stats': {
                'total': total_lines,
                'active': active_lines,
                'suspended': suspended_lines,
                'inactive': inactive_lines
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def chatbot_message(request):
    """Handle chatbot messages and process commands"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        account_id = data.get('account_id')
        conversation_history = data.get('conversation_history', [])
        
        if not message or not account_id:
            return JsonResponse({'error': 'Message and account_id are required'}, status=400)
        
        # Validate account exists
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return JsonResponse({'error': 'Account not found'}, status=404)
        
        # Process message with chatbot (pass conversation history for context)
        result = chatbot.process_message(message, account_id, conversation_history)
        
        return JsonResponse({
            'response': result.get('response', ''),
            'tool_result': result.get('tool_result'),
            'refresh_needed': result.get('refresh_needed', False),
            'trigger_modal': result.get('trigger_modal'),
            'line_to_mirror': result.get('line_to_mirror'),
            'line_to_mirror_data': result.get('line_to_mirror_data'),
            'success': True
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_line_details(request):
    """Update employee name and payment due date for a specific line"""
    try:
        data = json.loads(request.body)
        line_id = data.get('line_id')
        employee_name = data.get('employee_name')
        payment_date_str = data.get('payment_date')
        
        if not line_id or not employee_name or not payment_date_str:
            return JsonResponse({'error': 'line_id, employee_name, and payment_date are required'}, status=400)
        
        # Validate line exists
        try:
            line = Line.objects.get(id=line_id)
        except Line.DoesNotExist:
            return JsonResponse({'error': 'Line not found'}, status=404)
        
        # Parse and validate date
        try:
            from datetime import datetime
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        
        # Update the line
        old_employee_name = line.employee_name
        old_payment_date = line.payment_due_date
        line.employee_name = employee_name
        line.payment_due_date = payment_date
        line.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Line details updated successfully',
            'line': {
                'id': line.id,
                'line_name': line.line_name,
                'old_employee_name': old_employee_name,
                'new_employee_name': employee_name,
                'old_payment_date': old_payment_date.isoformat() if old_payment_date else None,
                'new_payment_date': payment_date.isoformat()
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_line_payment_date(request):
    """Update payment due date for a specific line"""
    try:
        data = json.loads(request.body)
        line_id = data.get('line_id')
        payment_date_str = data.get('payment_date')
        
        if not line_id or not payment_date_str:
            return JsonResponse({'error': 'line_id and payment_date are required'}, status=400)
        
        # Validate line exists
        try:
            line = Line.objects.get(id=line_id)
        except Line.DoesNotExist:
            return JsonResponse({'error': 'Line not found'}, status=404)
        
        # Parse and validate date
        try:
            from datetime import datetime
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        
        # Update the line
        old_date = line.payment_due_date
        line.payment_due_date = payment_date
        line.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Payment due date updated successfully',
            'line': {
                'id': line.id,
                'line_name': line.line_name,
                'employee_name': line.employee_name,
                'old_payment_date': old_date.isoformat() if old_date else None,
                'new_payment_date': payment_date.isoformat()
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
def add_line_account_selection(request):
    """Display account selection page for Add A Line flow"""
    # Get all active accounts
    accounts = Account.objects.filter(status='ACTIVE').order_by('account_number')
    
    # Add line counts to each account
    for account in accounts:
        account.total_lines = account.lines.count()
        account.active_lines = account.lines.filter(status='ACTIVE').count()
        account.suspended_lines = account.lines.filter(status='SUSPENDED').count()
        account.cancelled_lines = account.lines.filter(status='CANCELLED').count()
    
    context = {
        'accounts': accounts,
        'total_accounts': accounts.count(),
    }
    return render(request, 'demo_app/add_line_account_selection.html', context)


@login_required
def logo_test(request):
    """Test page to verify logo visibility"""
    from django.conf import settings
    
    context = {
        'debug': settings.DEBUG,
        'static_url': settings.STATIC_URL,
        'static_root': settings.STATIC_ROOT,
    }
    return render(request, 'logo_test.html', context)
