from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'games', views.GameViewSet, basename='game-api')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Web UI endpoints
    path('', TemplateView.as_view(template_name='WebChessStats/home.html'), name='home'),
    path('games/', TemplateView.as_view(template_name='WebChessStats/game_list.html'), name='game_list'),
    path('game/<int:game_id>/', TemplateView.as_view(template_name='WebChessStats/game_detail.html'), 
         name='game_detail', kwargs={'game_id': 0}),
    path('import/', TemplateView.as_view(template_name='WebChessStats/import.html'), name='import_games'),
    path('stats/', TemplateView.as_view(template_name='WebChessStats/stats.html'), name='stats'),
    path('game/<int:game_id>/', views.game_detail_view, name='game_detail'),
    path('game/create/', views.game_create_view, name='game_create'),
]