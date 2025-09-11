# engineering_office/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from core.views import MyTokenObtainPairView
from django.conf import settings # <-- Import
from django.conf.urls.static import static # <-- Import
urlpatterns = [
    path('admin/', admin.site.urls),
    # مسارات الـ API الأساسية للتطبيق
    path('api/', include('core.urls')),
    
    # مسارات JWT للحصول على التوكن وتحديثه
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)