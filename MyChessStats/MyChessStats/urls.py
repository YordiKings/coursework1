from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('WebChessStats.urls')),  # This includes all our URLs
]