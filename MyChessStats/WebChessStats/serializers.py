from rest_framework import serializers
from .models import Game
import json

class GameSerializer(serializers.ModelSerializer):
    """Full Game serializer for CRUD operations"""
    opponent = serializers.SerializerMethodField()
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    win_method_display = serializers.CharField(source='get_win_method_display', read_only=True)
    
    class Meta:
        model = Game
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'id']
    
    def get_opponent(self, obj):
        return obj.get_opponent()
    
    def validate_my_rating(self, value):
        if value and (value < 0 or value > 3500):
            raise serializers.ValidationError("Rating must be between 0 and 3500")
        return value
    
    def validate_move_count(self, value):
        if value and value < 0:
            raise serializers.ValidationError("Move count cannot be negative")
        return value

class GameListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    opponent = serializers.SerializerMethodField()
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    
    class Meta:
        model = Game
        fields = [
            'id', 'platform', 'date_played', 'white_player', 'black_player',
            'my_color', 'result', 'result_display', 'opponent', 'my_rating',
            'opponent_rating', 'opening', 'time_class', 'move_count', 'is_active'
        ]
    
    def get_opponent(self, obj):
        return obj.get_opponent()

class GameCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new games"""
    
    class Meta:
        model = Game
        exclude = ['created_at', 'updated_at', 'moves_with_eval']

class GameImportSerializer(serializers.Serializer):
    """Serializer for bulk import from CSV/PGN"""
    file = serializers.FileField()
    platform = serializers.ChoiceField(choices=['chesscom', 'lichess'])
    username = serializers.CharField(required=False, allow_blank=True, 
                                    help_text="Your username on this platform (required for Lichess)")
    
    def validate(self, data):
        """Validate based on platform"""
        platform = data.get('platform')
        username = data.get('username')
        
        if platform == 'lichess' and not username:
            raise serializers.ValidationError(
                {"username": "Username is required for Lichess imports"}
            )
        return data
    
    def validate_file(self, value):
        platform = self.initial_data.get('platform')
        if platform == 'chesscom':
            if not value.name.endswith('.csv'):
                raise serializers.ValidationError("Chess.com imports require CSV files")
        elif platform == 'lichess':
            if not value.name.endswith('.pgn'):
                raise serializers.ValidationError("Lichess imports require PGN files")
        return value

class GameStatsSerializer(serializers.Serializer):
    """Serializer for statistics response"""
    total_games = serializers.IntegerField()
    wins = serializers.IntegerField()
    losses = serializers.IntegerField()
    draws = serializers.IntegerField()
    win_percentage = serializers.FloatField()
    by_platform = serializers.ListField()
    top_openings = serializers.ListField()
    rating_progression = serializers.ListField()