from django.contrib import admin
from .models import Game

admin.site.register(Game)
class GameAdmin(admin.ModelAdmin):

    list_display = ['id', 'date_played', 'white_player', 'black_player', 'result', 'user']
    list_filter = ['platform', 'result', 'user']
    search_fields = ['white_player', 'black_player']