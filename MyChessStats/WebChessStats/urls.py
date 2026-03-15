"""
URL configuration for mychessstats project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView



# Import local views
from WebChessStats import views

# REST Framework router configuration
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'games', views.GameViewSet, basename='game-api')

urlpatterns = [
    # ============ ADMIN ============
    path('admin/', admin.site.urls),
    
    # ============ AUTHENTICATION ============
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    
    # Django's built-in auth URLs (optional - uncomment if needed)
    # path('accounts/', include('django.contrib.auth.urls')),
    
    # ============ PUBLIC PAGES ============
    path('', views.home_view, name='home'),
    
    # ============ PROTECTED PAGES (require login) ============
    path('games/', views.game_list_view, name='game_list'),
    path('game/<int:game_id>/', views.game_detail_view, name='game_detail'),
    path('game/<int:game_id>/edit/', views.game_edit_view, name='game_edit'),
    path('import/', views.import_view, name='import_games'),
    path('stats/', views.stats_view, name='stats'),
    
    # ============ BOARD VISUALIZATION ============
    path('game/<int:game_id>/board/', views.game_board_view, name='game-board'),
    
    # ============ API ENDPOINTS ============
    # REST Framework API (includes all CRUD endpoints)
    path('api/', include(router.urls)),
    
    # API authentication endpoints (for DRF browsable API)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # Direct delete-all endpoint (alternative to DRF action)
    path('api/delete-all-games/', views.delete_all_games_direct, name='delete-all-direct'),
    
    path('api/docs/', TemplateView.as_view(template_name='WebChessStats/api_docs.html'), name='api-docs'),
]