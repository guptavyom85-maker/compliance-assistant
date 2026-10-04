"""
URL configuration for compliance_assistant project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('qa.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]

# Private documents are served through the authenticated document_file view.
