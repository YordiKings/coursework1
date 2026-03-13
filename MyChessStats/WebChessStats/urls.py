from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'games', views.GameViewSet, basename='game-api')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Test endpoint
    path('test-ajax/', views.test_ajax, name='test_ajax'),
    
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Protected web UI endpoints
    path('', views.home_view, name='home'),
    path('games/', views.game_list_view, name='game_list'),
    path('game/<int:game_id>/', views.game_detail_view, name='game_detail'),
    path('game/create/', views.game_create_view, name='game_create'),
    path('import/', views.import_view, name='import_games'),
    path('stats/', views.stats_view, name='stats'),
]