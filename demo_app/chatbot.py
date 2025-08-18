"""
AI-powered chatbot service with OpenAI function calling for T-Mobile account management.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models
from django.conf import settings
from decimal import Decimal
from datetime import timedelta
import uuid

import openai
from .models import Account, Line, Service, LineService

# Configure logging
logger = logging.getLogger(__name__)

# OpenAI API key will be used directly in the client


# Tool functions for OpenAI function calling
def add_service_to_lines(account_id: int, service_type: str, line_identifiers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Add a service to one or more lines in a T-Mobile account.
    
    Args:
        account_id: The account ID to add services to
        service_type: Type of service to add (e.g., "1_day", "10_day", "30_day", "international_pass")
        line_identifiers: List of line identifiers (names, MSNDs, employee names/numbers, etc.). If None, adds to all lines.
    
    Returns:
        Dict containing success status, results, and metadata
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        # If no specific service type provided, trigger the Add Service modal
        if not service_type or service_type.strip() == "":
            return {
                "success": True,
                "results": ["Opening Add Service modal..."],
                "trigger_modal": "add_service",
                "account_id": account_id,
                "account_number": account.account_number
            }
        
        # Find the service
        service = _find_service(service_type)
        if not service:
            return {
                "success": False, 
                "error": f"Service type '{service_type}' not found. Available options:\n• 1-day International Pass ($1)\n• 10-day International Pass ($35)\n• 30-day International Pass ($50)",
                "available_services": [
                    {"name": "1-day International Pass", "price": "$1", "data": "512MB", "duration": "1 day"},
                    {"name": "10-day International Pass", "price": "$35", "data": "5GB", "duration": "10 days"},
                    {"name": "30-day International Pass", "price": "$50", "data": "15GB", "duration": "30 days"}
                ],
                "needs_clarification": True
            }
        
        # Find the lines
        lines = _find_lines(account, line_identifiers)
        if not lines:
            return {"success": False, "error": "No matching lines found"}
        
        # Add service to lines
        results = []
        successful_additions = 0
        
        for line in lines:
            # Check if service already exists
            existing = LineService.objects.filter(
                line=line,
                service=service,
                status__in=['PENDING', 'ACTIVE']
            ).exists()
            
            if existing:
                results.append(f"❌ {line.line_name}: Service already active")
                continue
            
            # Calculate pricing
            base_price = service.price
            tax_amount = base_price * Decimal('0.08')
            total_amount = base_price + tax_amount
            expires_at = timezone.now() + timedelta(days=service.duration_days)
            
            # Create LineService
            line_service = LineService.objects.create(
                line=line,
                service=service,
                status='ACTIVE',
                activated_at=timezone.now(),
                expires_at=expires_at,
                amount_paid=base_price,
                tax_amount=tax_amount,
                total_amount=total_amount,
                payment_method='AI Assistant',
                transaction_id=str(uuid.uuid4())[:8].upper()
            )
            
            results.append(f"✅ {line.line_name}: {service.name} added successfully (${total_amount})")
            successful_additions += 1
        
        # Calculate total cost
        total_cost = float(service.price + (service.price * Decimal('0.08'))) * successful_additions
        
        return {
            "success": True,
            "results": results,
            "service_name": service.name,
            "total_cost": total_cost,
            "lines_affected": successful_additions
        }
        
    except Exception as e:
        logger.error(f"Error adding service: {str(e)}")
        return {"success": False, "error": str(e)}


def list_account_lines(account_id: int, status_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    List all lines in a T-Mobile account.
    
    Args:
        account_id: The account ID to list lines for
        status_filter: Optional status filter ("active", "suspended", etc.)
    
    Returns:
        Dict containing lines data and summary
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        lines = account.lines.all()
        
        if status_filter:
            lines = lines.filter(status__icontains=status_filter.upper())
        
        line_data = []
        for line in lines:
            active_services = LineService.objects.filter(
                line=line,
                status__in=['PENDING', 'ACTIVE']
            ).select_related('service')
            
            services_info = []
            for ls in active_services:
                exp_date = ls.expires_at.strftime('%Y-%m-%d') if ls.expires_at else 'No expiration'
                services_info.append(f"{ls.service.name} (expires: {exp_date})")
            
            line_data.append({
                "name": line.line_name,
                "msdn": line.msdn,
                "employee": line.employee_name,
                "employee_number": line.employee_number,
                "status": line.get_status_display(),
                "services": services_info,
                "added_on": line.added_on.strftime('%Y-%m-%d')
            })
        
        return {
            "success": True,
            "lines": line_data,
            "total_lines": len(line_data)
        }
        
    except Exception as e:
        logger.error(f"Error listing lines: {str(e)}")
        return {"success": False, "error": str(e)}


def get_account_summary(account_id: int) -> Dict[str, Any]:
    """
    Get comprehensive account information and statistics.
    
    Args:
        account_id: The account ID to get information for
    
    Returns:
        Dict containing account details and statistics
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        total_lines = account.lines.count()
        active_lines = account.lines.filter(status='ACTIVE').count()
        suspended_lines = account.lines.filter(status='SUSPENDED').count()
        
        # Get recent service additions
        recent_services = LineService.objects.filter(
            line__account=account,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Calculate total monthly spend on services
        active_line_services = LineService.objects.filter(
            line__account=account,
            status='ACTIVE'
        )
        total_monthly_cost = sum(ls.total_amount for ls in active_line_services)
        
        return {
            "success": True,
            "account_number": account.account_number,
            "status": account.get_status_display(),
            "account_type": account.get_account_type_display(),
            "total_lines": total_lines,
            "active_lines": active_lines,
            "suspended_lines": suspended_lines,
            "recent_services": recent_services,
            "total_monthly_cost": float(total_monthly_cost),
            "created_on": account.created_on.strftime('%Y-%m-%d'),
            "last_modified": account.last_modified_on.strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        logger.error(f"Error getting account info: {str(e)}")
        return {"success": False, "error": str(e)}


def suspend_lines(account_id: int, line_identifiers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Suspend one or more lines in a T-Mobile account.
    
    Args:
        account_id: The account ID to suspend lines in
        line_identifiers: List of line identifiers (names, MSNDs, employee names/numbers, etc.). If None, suspends all active lines.
    
    Returns:
        Dict containing success status, results, and metadata
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        # Log the search attempt
        logger.info(f"Attempting to suspend lines in account {account_id}. Line identifiers: {line_identifiers}")
        
        # If no specific identifiers provided, ask for clarification
        if not line_identifiers:
            # Get all active lines to show options
            all_active_lines = account.lines.filter(status='ACTIVE')
            if all_active_lines.count() > 1:
                return {
                    "success": False,
                    "error": "Please specify which line(s) you want to suspend. You can mention the employee name, phone number, or line name.",
                    "available_lines": [
                        {
                            "line_name": line.line_name,
                            "employee_name": line.employee_name,
                            "msdn": line.msdn,
                            "employee_number": line.employee_number
                        } for line in all_active_lines
                    ],
                    "total_active_lines": all_active_lines.count(),
                    "needs_clarification": True
                }
            elif all_active_lines.count() == 1:
                # Only one active line, proceed with suspension
                line = all_active_lines.first()
                line.status = 'SUSPENDED'
                line.save()
                
                return {
                    "success": True,
                    "results": [f"✅ {line.line_name} ({line.msdn}): Suspended successfully"],
                    "lines_suspended": 1,
                    "total_lines": 1,
                    "account_id": account_id,
                    "auto_suspended": True
                }
            else:
                return {
                    "success": False,
                    "error": "No active lines found to suspend in this account."
                }
        
        # Find the lines
        lines = _find_lines(account, line_identifiers)
        logger.info(f"Found {len(lines)} lines for account {account_id}")
        
        if not lines:
            # Provide more detailed error information
            all_lines = account.lines.all()
            available_identifiers = []
            for line in all_lines:
                available_identifiers.extend([
                    line.line_name,
                    line.msdn,
                    line.employee_name,
                    line.employee_number
                ])
            
            return {
                "success": False, 
                "error": f"No matching lines found for identifiers: {line_identifiers}",
                "available_identifiers": available_identifiers,
                "total_lines_in_account": all_lines.count(),
                "needs_clarification": True
            }
        
        # If multiple lines found, ask for clarification
        if len(lines) > 1:
            return {
                "success": False,
                "error": f"Multiple lines found matching '{', '.join(line_identifiers)}'. Please be more specific about which line to suspend.",
                "matching_lines": [
                    {
                        "line_name": line.line_name,
                        "employee_name": line.employee_name,
                        "msdn": line.msdn,
                        "employee_number": line.employee_number,
                        "status": line.status
                    } for line in lines
                ],
                "total_matches": len(lines),
                "needs_clarification": True
            }
        
        # Filter to only active lines (can only suspend active lines)
        active_lines = [line for line in lines if line.status == 'ACTIVE']
        
        if not active_lines:
            # Show what was found but couldn't be suspended
            status_breakdown = {}
            for line in lines:
                status = line.status
                if status not in status_breakdown:
                    status_breakdown[status] = []
                status_breakdown[status].append(line.line_name)
            
            return {
                "success": False, 
                "error": f"No active lines found to suspend. Found lines with statuses: {status_breakdown}",
                "lines_found": len(lines),
                "active_lines": 0
            }
        
        # Suspend lines
        results = []
        successful_suspensions = 0
        
        for line in active_lines:
            try:
                line.status = 'SUSPENDED'
                line.save()
                
                results.append(f"✅ {line.line_name} ({line.msdn}): Suspended successfully")
                successful_suspensions += 1
                logger.info(f"Successfully suspended line {line.id} ({line.line_name})")
            except Exception as e:
                logger.error(f"Failed to suspend line {line.id}: {str(e)}")
                results.append(f"❌ {line.line_name} ({line.msdn}): Failed to suspend - {str(e)}")
        
        return {
            "success": True,
            "results": results,
            "lines_suspended": successful_suspensions,
            "total_lines": len(active_lines),
            "account_id": account_id
        }
        
    except Exception as e:
        logger.error(f"Error suspending lines: {str(e)}")
        return {"success": False, "error": str(e)}


def restore_lines(account_id: int, line_identifiers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Restore one or more suspended lines in a T-Mobile account.
    
    Args:
        account_id: The account ID to restore lines in
        line_identifiers: List of line identifiers (names, MSNDs, employee names/numbers, etc.). If None, restores all suspended lines.
    
    Returns:
        Dict containing success status, results, and metadata
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        # Log the restore attempt
        logger.info(f"Attempting to restore lines in account {account_id}. Line identifiers: {line_identifiers}")
        
        # Find the lines - specifically look for suspended lines if no identifiers provided
        if not line_identifiers:
            lines = _find_lines(account, status_filter='SUSPENDED')
            logger.info(f"Looking for all suspended lines in account {account_id}")
        else:
            lines = _find_lines(account, line_identifiers)
            logger.info(f"Looking for specific lines with identifiers: {line_identifiers}")
            
        logger.info(f"Found {len(lines)} lines for account {account_id}")
        
        if not lines:
            # Provide more detailed error information
            all_lines = account.lines.all()
            status_breakdown = {}
            for line in all_lines:
                status = line.status
                if status not in status_breakdown:
                    status_breakdown[status] = []
                status_breakdown[status].append(line.line_name)
            
            return {
                "success": False, 
                "error": f"No matching lines found for identifiers: {line_identifiers}",
                "status_breakdown": status_breakdown,
                "total_lines_in_account": all_lines.count()
            }
        
        # Filter to only suspended lines (can only restore suspended lines)
        suspended_lines = [line for line in lines if line.status == 'SUSPENDED']
        logger.info(f"Found {len(suspended_lines)} suspended lines out of {len(lines)} total lines")
        
        if not suspended_lines:
            # Show what was found but couldn't be restored
            status_breakdown = {}
            for line in lines:
                status = line.status
                if status not in status_breakdown:
                    status_breakdown[status] = []
                status_breakdown[status].append(line.line_name)
            
            return {
                "success": False, 
                "error": f"No suspended lines found to restore. Found lines with statuses: {status_breakdown}",
                "lines_found": len(lines),
                "suspended_lines": 0
            }
        
        # Restore lines
        results = []
        successful_restorations = 0
        
        for line in suspended_lines:
            line.status = 'ACTIVE'
            line.save()
            
            results.append(f"✅ {line.line_name} ({line.msdn}): Restored successfully")
            successful_restorations += 1
        
        return {
            "success": True,
            "results": results,
            "lines_restored": successful_restorations,
            "total_lines": len(suspended_lines)
        }
        
    except Exception as e:
        logger.error(f"Error restoring lines: {str(e)}")
        return {"success": False, "error": str(e)}


def reactivate_cancelled_lines(account_id: int, line_identifiers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Reactivate one or more cancelled lines in a T-Mobile account.
    
    Args:
        account_id: The account ID to reactivate lines in
        line_identifiers: List of line identifiers (names, MSNDs, employee names/numbers, etc.). If None, reactivates all cancelled lines.
    
    Returns:
        Dict containing success status, results, and metadata
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        # Log the reactivation attempt
        logger.info(f"Attempting to reactivate cancelled lines in account {account_id}. Line identifiers: {line_identifiers}")
        
        # Find the lines - specifically look for cancelled lines if no identifiers provided
        if not line_identifiers:
            lines = _find_lines(account, status_filter='CANCELLED')
        else:
            lines = _find_lines(account, line_identifiers)
            
        logger.info(f"Found {len(lines)} lines for account {account_id}")
        
        if not lines:
            # Provide more detailed error information
            all_lines = account.lines.all()
            available_identifiers = []
            for line in all_lines:
                available_identifiers.extend([
                    line.line_name,
                    line.msdn,
                    line.employee_name,
                    line.employee_number
                ])
            
            return {
                "success": False, 
                "error": f"No matching lines found for identifiers: {line_identifiers}",
                "available_identifiers": available_identifiers,
                "total_lines_in_account": all_lines.count()
            }
        
        # Filter to only cancelled lines (can only reactivate cancelled lines)
        cancelled_lines = [line for line in lines if line.status == 'CANCELLED']
        
        if not cancelled_lines:
            # Show what was found but couldn't be reactivated
            status_breakdown = {}
            for line in lines:
                status = line.status
                if status not in status_breakdown:
                    status_breakdown[status] = []
                status_breakdown[status].append(line.line_name)
            
            return {
                "success": False, 
                "error": f"No cancelled lines found to reactivate. Found lines with statuses: {status_breakdown}",
                "lines_found": len(lines),
                "cancelled_lines": 0
            }
        
        # Reactivate lines
        results = []
        successful_reactivations = 0
        
        for line in cancelled_lines:
            try:
                # Reactivate the line
                line.status = 'ACTIVE'
                line.cancelled_on = None  # Clear cancellation date
                line.save()
                
                results.append(f"✅ {line.line_name} ({line.msdn}): Reactivated successfully")
                successful_reactivations += 1
                logger.info(f"Successfully reactivated line {line.id} ({line.line_name})")
            except Exception as e:
                logger.error(f"Failed to reactivate line {line.id}: {str(e)}")
                results.append(f"❌ {line.line_name} ({line.msdn}): Failed to reactivate - {str(e)}")
        
        return {
            "success": True,
            "results": results,
            "lines_reactivated": successful_reactivations,
            "total_lines": len(cancelled_lines),
            "account_id": account_id
        }
        
    except Exception as e:
        logger.error(f"Error reactivating cancelled lines: {str(e)}")
        return {"success": False, "error": str(e)}


def add_line_to_account(account_id: int, line_name: str = None, employee_name: str = None, employee_number: str = None) -> Dict[str, Any]:
    """
    Trigger the Add A Line modal for a T-Mobile account.
    
    Args:
        account_id: The account ID to add the line to
        line_name: Not used in modal flow
        employee_name: Not used in modal flow
        employee_number: Not used in modal flow
    
    Returns:
        Dict containing success status and modal trigger flag
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        return {
            "success": True,
            "results": ["Opening Add A Line modal..."],
            "trigger_modal": "add_line",
            "account_id": account_id,
            "account_number": account.account_number
        }
        
    except Exception as e:
        logger.error(f"Error triggering add line modal: {str(e)}")
        return {"success": False, "error": str(e)}


def mirror_line(account_id: int, line_identifier: str = None) -> Dict[str, Any]:
    """
    Trigger the Mirror Line modal for a T-Mobile account.
    
    Args:
        account_id: The account ID to mirror a line from
        line_identifier: The line to mirror (name, MSDN, employee name, etc.)
    
    Returns:
        Dict containing success status and modal trigger flag
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        # If a specific line is provided, find it
        line_to_mirror = None
        if line_identifier:
            line_to_mirror = _find_lines(account, [line_identifier])
            if line_to_mirror:
                line_to_mirror = line_to_mirror[0]
        
        return {
            "success": True,
            "results": ["Opening Mirror Line modal..."],
            "trigger_modal": "mirror_line",
            "account_id": account_id,
            "account_number": account.account_number,
            "line_to_mirror": line_to_mirror.id if line_to_mirror else None,
            "line_to_mirror_data": {
                "id": line_to_mirror.id,
                "line_name": line_to_mirror.line_name,
                "employee_name": line_to_mirror.employee_name,
                "msdn": line_to_mirror.msdn,
                "device_model": line_to_mirror.device_model,
                "device_color": line_to_mirror.device_color,
                "device_storage": line_to_mirror.device_storage,
                "plan_name": line_to_mirror.plan_name,
                "protection_name": line_to_mirror.protection_name
            } if line_to_mirror else None
        }
        
    except Exception as e:
        logger.error(f"Error triggering mirror line modal: {str(e)}")
        return {"success": False, "error": str(e)}


def upgrade_line(account_id: int, line_identifier: str = None) -> Dict[str, Any]:
    """
    Trigger the Upgrade Line modal for a T-Mobile account.
    
    Args:
        account_id: The account ID to upgrade a line in
        line_identifier: The line to upgrade (name, MSDN, employee name, etc.)
    
    Returns:
        Dict containing success status and modal trigger flag
    """
    try:
        account = get_object_or_404(Account, id=account_id)
        
        # If a specific line is provided, find it
        line_to_upgrade = None
        if line_identifier:
            line_to_upgrade = _find_lines(account, [line_identifier])
            if line_to_upgrade:
                line_to_upgrade = line_to_upgrade[0]
        
        return {
            "success": True,
            "results": ["Opening Upgrade Line modal..."],
            "trigger_modal": "upgrade_line",
            "account_id": account_id,
            "account_number": account.account_number,
            "line_to_upgrade": line_to_upgrade.id if line_to_upgrade else None,
            "line_to_upgrade_data": {
                "id": line_to_upgrade.id,
                "line_name": line_to_upgrade.line_name,
                "employee_name": line_to_upgrade.employee_name,
                "msdn": line_to_upgrade.msdn,
                "device_model": line_to_upgrade.device_model,
                "device_color": line_to_upgrade.device_color,
                "device_storage": line_to_upgrade.device_storage,
                "plan_name": line_to_upgrade.plan_name,
                "protection_name": line_to_upgrade.protection_name
            } if line_to_upgrade else None
        }
        
    except Exception as e:
        logger.error(f"Error triggering upgrade line modal: {str(e)}")
        return {"success": False, "error": str(e)}


def _find_service(service_type: str) -> Optional[Service]:
    """Find service by type or keywords"""
    service_type = service_type.lower()
    
    # Direct type mapping
    type_mapping = {
        "1_day": {"duration_days": 1},
        "10_day": {"duration_days": 10},
        "30_day": {"duration_days": 30},
        "international_pass": {"service_type": "INTERNATIONAL_PASS"}
    }
    
    if service_type in type_mapping:
        return Service.objects.filter(is_active=True, **type_mapping[service_type]).first()
    
    # Keyword matching
    if any(keyword in service_type for keyword in ['1 day', '1day', 'one day']):
        return Service.objects.filter(duration_days=1, is_active=True).first()
    elif any(keyword in service_type for keyword in ['10 day', '10day', 'ten day', 'week']):
        return Service.objects.filter(duration_days=10, is_active=True).first()
    elif any(keyword in service_type for keyword in ['30 day', '30day', 'thirty day', 'month']):
        return Service.objects.filter(duration_days=30, is_active=True).first()
    elif 'international' in service_type or 'pass' in service_type:
        return Service.objects.filter(service_type='INTERNATIONAL_PASS', is_active=True).first()
    
    # Try name search
    return Service.objects.filter(name__icontains=service_type, is_active=True).first()


def _find_lines(account: Account, line_identifiers: Optional[List[str]] = None, status_filter: Optional[str] = None) -> List[Line]:
    """Find lines by various identifiers"""
    if not line_identifiers:
        # Return all lines with optional status filter if no specific identifiers
        if status_filter:
            return list(account.lines.filter(status=status_filter))
        else:
            return list(account.lines.all())
    
    lines = []
    for identifier in line_identifiers:
        if not identifier or not identifier.strip():
            continue
            
        identifier = identifier.lower().strip()
        
        # Try to find by various fields with better matching
        line_matches = account.lines.filter(
            models.Q(line_name__icontains=identifier) |
            models.Q(msdn__icontains=identifier) |
            models.Q(employee_name__icontains=identifier) |
            models.Q(employee_number__icontains=identifier)
        )
        
        # If no matches found, try more flexible matching
        if not line_matches.exists():
            # Try partial matching for phone numbers
            if identifier.startswith('+1-') or identifier.startswith('555'):
                # Remove common prefixes and try matching
                clean_identifier = identifier.replace('+1-', '').replace('555-', '')
                if clean_identifier:
                    line_matches = account.lines.filter(
                        models.Q(msdn__icontains=clean_identifier)
                    )
            
            # Try matching employee names more flexibly
            if not line_matches.exists():
                # Split by spaces and try matching parts of names
                name_parts = identifier.split()
                for part in name_parts:
                    if len(part) > 2:  # Only search for parts longer than 2 chars
                        part_matches = account.lines.filter(
                            models.Q(employee_name__icontains=part)
                        )
                        if part_matches.exists():
                            line_matches = part_matches
                            break
        
        lines.extend(line_matches)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_lines = []
    for line in lines:
        if line.id not in seen:
            seen.add(line.id)
            unique_lines.append(line)
    
    return unique_lines


class AITMobileChatbot:
    """AI-powered T-Mobile chatbot using OpenAI function calling"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', None))
        
        # Define available functions for OpenAI
        self.functions = [
            {
                "name": "add_service_to_lines",
                "description": "Add a service (like international pass) to one or more phone lines",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to add services to"
                        },
                        "service_type": {
                            "type": "string",
                            "description": "Type of service to add",
                            "enum": ["1_day", "10_day", "30_day", "international_pass"]
                        },
                        "line_identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of line identifiers (names, phone numbers, employee names/numbers). Leave empty to add to all lines."
                        }
                    },
                    "required": ["account_id", "service_type"]
                }
            },
            {
                "name": "list_account_lines",
                "description": "List all phone lines in the account with their details and services",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to list lines for"
                        },
                        "status_filter": {
                            "type": "string",
                            "description": "Filter lines by status (active, suspended, etc.)",
                            "enum": ["active", "suspended", "inactive"]
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "get_account_summary",
                "description": "Get comprehensive account information and statistics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to get information for"
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "suspend_lines",
                "description": "Suspend one or more lines in a T-Mobile account. Can only suspend active lines.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to suspend lines in"
                        },
                        "line_identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of line identifiers (names, MSNDs, employee names/numbers, etc.). If None, suspends all active lines."
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "restore_lines",
                "description": "Restore one or more suspended lines in a T-Mobile account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to restore lines in"
                        },
                        "line_identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of line identifiers (names, MSNDs, employee names/numbers, etc.). If None, restores all suspended lines."
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "reactivate_cancelled_lines",
                "description": "Reactivate one or more cancelled lines in a T-Mobile account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to reactivate lines in"
                        },
                        "line_identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of line identifiers (names, MSNDs, employee names/numbers, etc.). If None, reactivates all cancelled lines."
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "add_line_to_account",
                "description": "Add a new line to the T-Mobile account",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to add the line to"
                        },
                        "line_name": {
                            "type": "string",
                            "description": "Name for the new line (e.g., 'Line 1', 'Primary Line'). If not provided, will generate automatically."
                        },
                        "employee_name": {
                            "type": "string",
                            "description": "Employee name for the line. If not provided, will use 'New Employee'."
                        },
                        "employee_number": {
                            "type": "string",
                            "description": "Employee number for the line. If not provided, will generate automatically."
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "mirror_line",
                "description": "Mirror an existing line to create a new line with the same details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to mirror a line from"
                        },
                        "line_identifier": {
                            "type": "string",
                            "description": "The line to mirror (name, MSDN, employee name, etc.). If not provided, user will select from available lines."
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "upgrade_line",
                "description": "Upgrade an existing line to a new plan or protection",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to upgrade a line in"
                        },
                        "line_identifier": {
                            "type": "string",
                            "description": "The line to upgrade (name, MSDN, employee name, etc.). If not provided, user will select from available lines."
                        }
                    },
                    "required": ["account_id"]
                }
            }
        ]
        
        # Function mapping
        self.function_map = {
            "add_service_to_lines": add_service_to_lines,
            "list_account_lines": list_account_lines,
            "get_account_summary": get_account_summary,
            "suspend_lines": suspend_lines,
            "restore_lines": restore_lines,
            "reactivate_cancelled_lines": reactivate_cancelled_lines,
            "add_line_to_account": add_line_to_account,
            "mirror_line": mirror_line,
            "upgrade_line": upgrade_line
        }
    
    def process_message(self, message: str, account_id: int, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Process user message using OpenAI with function calling
        
        Args:
            message: User's message
            account_id: Current account ID
            conversation_history: Previous conversation messages for context
            
        Returns:
            Dict with response, tool_result, and refresh_needed flag
        """
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key or api_key == 'your_openai_api_key_here':
            return {
                "response": "OpenAI API key not configured. Please set your API key in settings.py",
                "tool_result": None,
                "refresh_needed": False
            }
        
        try:
            # Create system message with context
            system_message = f"""You are a helpful T-Mobile customer service assistant. You can help manage phone lines and services for account ID {account_id}.

Available services:
- 1_day: 1 Day International Pass ($1, 512MB data)
- 10_day: 10 Day International Pass ($35, 5GB data) 
- 30_day: 30 Day International Pass ($50, 15GB data)
- international_pass: Any international pass (will choose best option)

You can:
1. Add services to specific lines or all lines
2. List all lines in the account
3. Get account summary and statistics
4. Suspend lines (temporarily disable service)
5. Restore lines (re-enable suspended lines)
6. Reactivate cancelled lines (restore permanently cancelled lines)
7. Add new lines to the account
8. Mirror existing lines to create new lines with the same details
9. Upgrade existing lines to new plans or protection

When users mention line identifiers, extract them carefully - they could be:
- Employee names (John, Sarah, Amanda, etc.)
- Phone numbers (+1-555-0123)
- Line names (Line 1, Line 2)
- Employee numbers (EMP001, etc.)

IMPORTANT: Always ask for clarification when the user's request is ambiguous:
- If they say "suspend a line" without specifying which one, ask them to specify the employee name, phone number, or line name
- If they say "add a service" without specifying which service, ask them to choose from: 1-day pass ($1), 10-day pass ($35), or 30-day pass ($50)
- If they say "upgrade a line" without specifying which one, ask them to specify the employee name, phone number, or line name
- If multiple lines match their request, show them the options and ask them to be more specific
- Never assume which line they want to suspend, upgrade, or which service they want to add - always ask for clarification

For line management operations:
- You can only suspend active lines
- You can only restore suspended lines
- You can only reactivate cancelled lines
- If no specific lines are mentioned, you can suspend all active lines, restore all suspended lines, or reactivate all cancelled lines

For service additions:
- Always confirm the service type, duration, and cost before proceeding
- Ask users to specify which service they want if they don't mention it
- Show pricing information: 1-day ($1), 10-day ($35), 30-day ($50)

For line upgrades:
- Users can upgrade device plans, protection plans, or both
- The upgrade modal will show current line details and available upgrade options
- Users can select specific lines to upgrade or upgrade all lines

Be helpful and confirm actions clearly. Maintain conversation context and refer to previous messages when relevant."""
            
            # Build messages array with conversation history
            messages = [{"role": "system", "content": system_message}]
            
            # Add conversation history for context (limit to last 10 messages to avoid token limits)
            if conversation_history:
                recent_history = conversation_history[-10:]  # Keep last 10 messages
                for msg in recent_history:
                    if msg.get('role') in ['user', 'assistant']:
                        messages.append({"role": msg['role'], "content": msg['content']})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Call OpenAI with function calling
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                functions=self.functions,
                function_call="auto",
                temperature=0.3
            )
            
            message_response = response.choices[0].message
            
            # Check if AI wants to call a function
            if message_response.function_call:
                function_name = message_response.function_call.name
                function_args = json.loads(message_response.function_call.arguments)
                
                # Add account_id if not present
                if 'account_id' not in function_args:
                    function_args['account_id'] = account_id
                
                # Execute the function
                if function_name in self.function_map:
                    function_result = self.function_map[function_name](**function_args)
                    
                    # Generate response based on function result
                    return self._format_function_response(function_name, function_result, message_response.content)
                else:
                    return {
                        "response": f"Unknown function: {function_name}",
                        "tool_result": None,
                        "refresh_needed": False
                    }
            else:
                # AI responded without calling functions
                return {
                    "response": message_response.content,
                    "tool_result": None,
                    "refresh_needed": False
                }
                
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                "response": f"I encountered an error processing your request: {str(e)}",
                "tool_result": None,
                "refresh_needed": False
            }
    
    def _format_function_response(self, function_name: str, result: Dict[str, Any], ai_content: Optional[str]) -> Dict[str, Any]:
        """Format the response based on function execution result"""
        
        if not result.get("success"):
            return {
                "response": f"I couldn't complete that action: {result.get('error', 'Unknown error')}",
                "tool_result": None,
                "refresh_needed": False
            }
        
        if function_name == "add_service_to_lines":
            # Check if modal should be triggered
            if result.get("trigger_modal") == "add_service":
                response = f"✅ Opening Add Service modal for Account #{result['account_number']}"
                tool_result = "\n".join(result["results"])
                return {
                    "response": response,
                    "tool_result": tool_result,
                    "refresh_needed": False,
                    "trigger_modal": result.get("trigger_modal")
                }
            # Check if clarification is needed
            elif result.get("needs_clarification"):
                if result.get("available_services"):
                    # Show available services for selection
                    services_info = []
                    for service in result["available_services"]:
                        services_info.append(f"• {service['name']} - {service['price']} ({service['data']} data, {service['duration']})")
                    
                    response = "I'd be happy to add a service to your lines! Please choose which service you want:"
                    tool_result = "\n".join(services_info)
                    return {
                        "response": response,
                        "tool_result": tool_result,
                        "refresh_needed": False,
                        "needs_clarification": True
                    }
                else:
                    # General clarification needed
                    response = f"I need more information to help you. {result.get('error', 'Please specify which service to add.')}"
                    tool_result = result.get("error", "Please specify which service to add.")
                    return {
                        "response": response,
                        "tool_result": tool_result,
                        "refresh_needed": False,
                        "needs_clarification": True
                    }
            else:
                # Normal successful service addition
                response = f"✅ Successfully added {result['service_name']} to {result['lines_affected']} line(s) for ${result['total_cost']:.2f}"
                tool_result = "\n".join(result["results"])
                return {
                    "response": response,
                    "tool_result": tool_result,
                    "refresh_needed": True
                }
            
        elif function_name == "list_account_lines":
            response = f"Found {result['total_lines']} lines in your account:"
            lines_summary = []
            for line in result["lines"]:
                services_text = ", ".join(line["services"]) if line["services"] else "No active services"
                lines_summary.append(f"• {line['name']} ({line['employee']}) - {line['msdn']} - {services_text}")
            
            tool_result = "\n".join(lines_summary)
            return {
                "response": response,
                "tool_result": tool_result,
                "refresh_needed": False
            }
            
        elif function_name == "get_account_summary":
            response = "Here's your account summary:"
            tool_result = f"""Account #{result['account_number']} ({result['account_type']})
Status: {result['status']}
Total Lines: {result['total_lines']} ({result['active_lines']} active, {result['suspended_lines']} suspended)
Recent Services: {result['recent_services']} added in last 30 days
Monthly Service Cost: ${result['total_monthly_cost']:.2f}
Account Created: {result['created_on']}
Last Modified: {result['last_modified']}"""
            return {
                "response": response,
                "tool_result": tool_result,
                "refresh_needed": False
            }
            
        elif function_name == "suspend_lines":
            # Check if clarification is needed
            if result.get("needs_clarification"):
                if result.get("available_lines"):
                    # Show available lines for selection
                    lines_info = []
                    for line in result["available_lines"]:
                        lines_info.append(f"• {line['employee_name']} ({line['line_name']}) - {line['msdn']}")
                    
                    response = f"I found {result['total_active_lines']} active lines in your account. Please specify which line you want to suspend:"
                    tool_result = "\n".join(lines_info)
                    return {
                        "response": response,
                        "tool_result": tool_result,
                        "refresh_needed": False,
                        "needs_clarification": True
                    }
                elif result.get("matching_lines"):
                    # Show matching lines for clarification
                    lines_info = []
                    for line in result["matching_lines"]:
                        lines_info.append(f"• {line['employee_name']} ({line['line_name']}) - {line['msdn']} - Status: {line['status']}")
                    
                    response = f"I found {result['total_matches']} lines matching your request. Please be more specific about which line to suspend:"
                    tool_result = "\n".join(lines_info)
                    return {
                        "response": response,
                        "tool_result": tool_result,
                        "refresh_needed": False,
                        "needs_clarification": True
                    }
                else:
                    # General clarification needed
                    response = f"I need more information to help you. {result.get('error', 'Please specify which line to suspend.')}"
                    tool_result = result.get("error", "Please specify which line to suspend.")
                    return {
                        "response": response,
                        "tool_result": tool_result,
                        "refresh_needed": False,
                        "needs_clarification": True
                    }
            elif result.get("auto_suspended"):
                # Auto-suspended the only available line
                response = f"✅ I've suspended the only active line in your account: {result['results'][0]}"
                tool_result = "\n".join(result["results"])
                return {
                    "response": response,
                    "tool_result": tool_result,
                    "refresh_needed": True
                }
            else:
                # Normal successful suspension
                response = f"✅ Successfully suspended {result['lines_suspended']} line(s)"
                tool_result = "\n".join(result["results"])
                return {
                    "response": response,
                    "tool_result": tool_result,
                    "refresh_needed": True
                }
            
        elif function_name == "restore_lines":
            response = f"✅ Successfully restored {result['lines_restored']} line(s)"
            tool_result = "\n".join(result["results"])
            return {
                "response": response,
                "tool_result": tool_result,
                "refresh_needed": True
            }
            
        elif function_name == "reactivate_cancelled_lines":
            response = f"✅ Successfully reactivated {result['lines_reactivated']} line(s)"
            tool_result = "\n".join(result["results"])
            return {
                "response": response,
                "tool_result": tool_result,
                "refresh_needed": True
            }
            
        elif function_name == "add_line_to_account":
            response = f"✅ Opening Add A Line modal for Account #{result['account_number']}"
            tool_result = "\n".join(result["results"])
            return {
                "response": response,
                "tool_result": tool_result,
                "refresh_needed": False,
                "trigger_modal": result.get("trigger_modal")
            }
            
        elif function_name == "mirror_line":
            response = f"✅ Opening Mirror Line modal for Account #{result['account_number']}"
            tool_result = "\n".join(result["results"])
            return {
                "response": response,
                "tool_result": tool_result,
                "refresh_needed": False,
                "trigger_modal": result.get("trigger_modal"),
                "line_to_mirror": result.get("line_to_mirror"),
                "line_to_mirror_data": result.get("line_to_mirror_data")
            }
        
        elif function_name == "upgrade_line":
            response = f"✅ Opening Upgrade Line modal for Account #{result['account_number']}"
            tool_result = "\n".join(result["results"])
            return {
                "response": response,
                "tool_result": tool_result,
                "refresh_needed": False,
                "trigger_modal": result.get("trigger_modal"),
                "line_to_upgrade": result.get("line_to_upgrade"),
                "line_to_upgrade_data": result.get("line_to_upgrade_data")
            }
        
        return {
            "response": "Action completed successfully",
            "tool_result": json.dumps(result, indent=2),
            "refresh_needed": False
        }


# Create global AI chatbot instance
chatbot = AITMobileChatbot()