from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class Account(models.Model):
    """Account model representing a T-Mobile account"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]
    
    TYPE_CHOICES = [
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
        ('BUSINESS', 'Business'),
    ]
    
    account_number = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='STANDARD')
    created_on = models.DateTimeField(auto_now_add=True)
    last_modified_on = models.DateTimeField(auto_now=True)
    last_payment_date = models.DateField(null=True, blank=True)
    payment_due_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Account {self.account_number}"
    
    @property
    def number_of_lines(self):
        return self.lines.count()
    
    def save(self, *args, **kwargs):
        """Override save to ensure line status consistency"""
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            try:
                old_instance = Account.objects.get(pk=self.pk)
                old_status = old_instance.status
            except Account.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # If account status changed to INACTIVE, make all lines cancelled
        if old_status and old_status != self.status and self.status == 'INACTIVE':
            self.lines.update(status='CANCELLED')
    
    def update_status(self, new_status):
        """Update account status and handle line status changes"""
        if new_status == 'INACTIVE':
            # If account becomes inactive, make all lines cancelled
            self.lines.update(status='CANCELLED')
        elif new_status == 'ACTIVE':
            # If account becomes active, we could optionally reactivate lines
            # For now, we'll leave line statuses as they are
            pass
        
        self.status = new_status
        self.save()


class Service(models.Model):
    """Service model representing available services like International Passes"""
    
    SERVICE_TYPE_CHOICES = [
        ('INTERNATIONAL_PASS', 'International Pass'),
        ('DATA_ADDON', 'Data Add-on'),
        ('CALLING_ADDON', 'Calling Add-on'),
    ]
    
    name = models.CharField(max_length=100)
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPE_CHOICES)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(help_text="Duration in days")
    data_allowance_mb = models.IntegerField(help_text="Data allowance in MB", null=True, blank=True)
    features = models.JSONField(default=list, help_text="List of features")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['price']


class Line(models.Model):
    """Line model representing individual phone lines"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='lines')
    line_name = models.CharField(max_length=50)
    msdn = models.CharField(max_length=20, unique=True, help_text="Mobile Station Directory Number")
    employee_name = models.CharField(max_length=100)
    employee_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    added_on = models.DateTimeField(auto_now_add=True)
    payment_due_date = models.DateField(null=True, blank=True)
    
    # Device, Plan, and Protection information
    device_model = models.CharField(max_length=100, null=True, blank=True)
    device_color = models.CharField(max_length=50, null=True, blank=True)
    device_storage = models.CharField(max_length=50, null=True, blank=True)
    device_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    plan_name = models.CharField(max_length=100, null=True, blank=True)
    plan_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    plan_data_limit = models.CharField(max_length=50, null=True, blank=True)
    
    protection_name = models.CharField(max_length=100, null=True, blank=True)
    protection_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    trade_in_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_monthly_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.line_name} - {self.msdn}"
    
    class Meta:
        ordering = ['line_name']


class LineService(models.Model):
    """Junction table for Line and Service with activation details"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name='line_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='line_services')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Credit Card')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.line.line_name} - {self.service.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total amount if not provided
        if not self.total_amount:
            self.total_amount = self.amount_paid + self.tax_amount
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']
