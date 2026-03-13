from django.contrib import admin
from .models import Game

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['id', 'date_played', 'white_player', 'black_player', 
                   'result', 'opening', 'platform']
    list_filter = ['platform', 'result', 'time_class', 'my_color', 'date_played']
    search_fields = ['white_player', 'black_player', 'opponent_name', 'opening']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('platform', 'game_id', 'date_played', 'time_class')
        }),
        ('Players', {
            'fields': ('white_player', 'black_player', 'my_color', 'opponent_name')
        }),
        ('Result', {
            'fields': ('result', 'win_method', 'termination', 'outcome')
        }),
        ('Ratings', {
            'fields': ('my_rating', 'opponent_rating', 'rating_change')
        }),
        ('Opening', {
            'fields': ('eco', 'opening', 'opening_url')
        }),
        ('Game Data', {
            'fields': ('fen', 'pgn', 'move_count', 'my_accuracy', 'opponent_accuracy')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'is_active')
        }),
    )