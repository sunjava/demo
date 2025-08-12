"""
URL configuration for demo project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from demo_app.views import (
    hello_world, account_details, all_accounts, all_lines, login_view, logout_view, signup_view,
    get_services, add_service_to_lines, get_line_services, get_account_lines,
    suspend_lines, restore_lines, chatbot_message, create_line, update_account_status,
    add_line_account_selection, update_line_payment_date, update_line_details, create_mirrored_line,
    get_line_details, logo_test
)

urlpatterns = [
    path('', hello_world, name='hello_world'),
    path('dashboard/', hello_world, name='dashboard'),
    path('admin/', admin.site.urls),
    path('accounts/', all_accounts, name='all_accounts'),
    path('lines/', all_lines, name='all_lines'),
    path('add-line/', add_line_account_selection, name='add_line_account_selection'),
    path('accounts/<int:account_id>/', account_details, name='account_details'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup_view, name='signup'),
    
    # API endpoints
    path('api/services/', get_services, name='get_services'),
    path('api/services/add/', add_service_to_lines, name='add_service_to_lines'),
    path('api/lines/<int:line_id>/services/', get_line_services, name='get_line_services'),
    path('api/accounts/<int:account_id>/lines/', get_account_lines, name='get_account_lines'),
    path('api/lines/suspend/', suspend_lines, name='suspend_lines'),
    path('api/lines/restore/', restore_lines, name='restore_lines'),
    path('api/lines/create/', create_line, name='create_line'),
    path('api/lines/mirror/', create_mirrored_line, name='create_mirrored_line'),
    path('api/lines/<int:line_id>/details/', get_line_details, name='get_line_details'),
    path('api/lines/update-payment-date/', update_line_payment_date, name='update_line_payment_date'),
    path('api/lines/update-details/', update_line_details, name='update_line_details'),
    path('api/chatbot/message/', chatbot_message, name='chatbot_message'),
    path('api/accounts/update-status/', update_account_status, name='update_account_status'),
    path('logo-test/', logo_test, name='logo_test'),
]
# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # In production, serve static files from STATIC_ROOT
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
