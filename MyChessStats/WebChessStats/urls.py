from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'games', views.GameViewSet, basename='game-api')

urlpatterns = [

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    
    # Protected web UI endpoints
    path('', views.home_view, name='home'),
    path('games/', views.game_list_view, name='game_list'),
    path('game/<int:game_id>/', views.game_detail_view, name='game_detail'),
    path('import/', views.import_view, name='import_games'),
    path('stats/', views.stats_view, name='stats'),
    path('game/<int:game_id>/board/', views.game_board_view, name='game-board'),
    # API endpoints - including direct delete
    path('api/', include(router.urls)),
    path('api/delete-all-games/', views.delete_all_games_direct, name='delete-all-direct'),
]