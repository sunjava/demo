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

# Set OpenAI API key
openai.api_key = getattr(settings, 'OPENAI_API_KEY', None)


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
        
        # Find the service
        service = _find_service(service_type)
        if not service:
            return {"success": False, "error": f"Service type '{service_type}' not found"}
        
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
        
        # Find the lines
        lines = _find_lines(account, line_identifiers)
        if not lines:
            return {"success": False, "error": "No matching lines found"}
        
        # Filter to only active lines (can only suspend active lines)
        active_lines = [line for line in lines if line.status == 'ACTIVE']
        
        if not active_lines:
            return {"success": False, "error": "No active lines found to suspend"}
        
        # Suspend lines
        results = []
        successful_suspensions = 0
        
        for line in active_lines:
            line.status = 'SUSPENDED'
            line.save()
            
            results.append(f"✅ {line.line_name} ({line.msdn}): Suspended successfully")
            successful_suspensions += 1
        
        return {
            "success": True,
            "results": results,
            "lines_suspended": successful_suspensions,
            "total_lines": len(active_lines)
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
        
        # Find the lines
        lines = _find_lines(account, line_identifiers)
        if not lines:
            return {"success": False, "error": "No matching lines found"}
        
        # Filter to only suspended lines (can only restore suspended lines)
        suspended_lines = [line for line in lines if line.status == 'SUSPENDED']
        
        if not suspended_lines:
            return {"success": False, "error": "No suspended lines found to restore"}
        
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


def _find_lines(account: Account, line_identifiers: Optional[List[str]] = None) -> List[Line]:
    """Find lines by various identifiers"""
    if not line_identifiers:
        # Return all active lines if no specific identifiers
        return list(account.lines.filter(status='ACTIVE'))
    
    lines = []
    for identifier in line_identifiers:
        identifier = identifier.lower().strip()
        
        # Try to find by various fields
        line_matches = account.lines.filter(
            models.Q(line_name__icontains=identifier) |
            models.Q(msdn__icontains=identifier) |
            models.Q(employee_name__icontains=identifier) |
            models.Q(employee_number__icontains=identifier)
        )
        
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
        self.client = openai.OpenAI(api_key=openai.api_key)
        
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
            }
        ]
        
        # Function mapping
        self.function_map = {
            "add_service_to_lines": add_service_to_lines,
            "list_account_lines": list_account_lines,
            "get_account_summary": get_account_summary,
            "suspend_lines": suspend_lines,
            "restore_lines": restore_lines
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
        if not openai.api_key or openai.api_key == 'your_openai_api_key_here':
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

When users mention line identifiers, extract them carefully - they could be:
- Employee names (John, Sarah, Amanda, etc.)
- Phone numbers (+1-555-0123)
- Line names (Line 1, Line 2)
- Employee numbers (EMP001, etc.)

For suspend/restore operations:
- You can only suspend active lines
- You can only restore suspended lines
- If no specific lines are mentioned, you can suspend all active lines or restore all suspended lines

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
        
        return {
            "response": "Action completed successfully",
            "tool_result": json.dumps(result, indent=2),
            "refresh_needed": False
        }


# Create global AI chatbot instance
chatbot = AITMobileChatbot()