from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/worker/', include('apps.worker.urls')),
    path('api/client/', include('apps.client.urls')),
]