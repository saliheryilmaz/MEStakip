"""
URL configuration for metis_admin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import HttpResponse

def redirect_to_login(request):
    return redirect('dashboard:login')

def healthcheck(request):
    """Simple healthcheck endpoint for Railway"""
    try:
        # Basit bir database check
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        return HttpResponse("OK", status=200, content_type="text/plain")
    except Exception as e:
        return HttpResponse(f"ERROR: {str(e)}", status=500, content_type="text/plain")

def debug_info(request):
    """Debug bilgileri için endpoint"""
    import sys
    import django
    from django.conf import settings
    
    info = []
    info.append(f"Python version: {sys.version}")
    info.append(f"Django version: {django.get_version()}")
    info.append(f"DEBUG: {settings.DEBUG}")
    info.append(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    info.append(f"DATABASE: {settings.DATABASES['default']['ENGINE']}")
    
    # Environment variables
    import os
    info.append(f"RAILWAY_ENVIRONMENT: {os.environ.get('RAILWAY_ENVIRONMENT', 'Not set')}")
    info.append(f"PORT: {os.environ.get('PORT', 'Not set')}")
    info.append(f"DATABASE_URL: {'Set' if os.environ.get('DATABASE_URL') else 'Not set'}")
    
    # Installed apps
    info.append(f"INSTALLED_APPS: {settings.INSTALLED_APPS}")
    
    return HttpResponse("\n".join(info), content_type="text/plain")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', redirect_to_login, name='home'),
    path('dashboard/', include('dashboard.urls')),
    path('health/', healthcheck, name='healthcheck'),
    path('debug/', debug_info, name='debug_info'),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
