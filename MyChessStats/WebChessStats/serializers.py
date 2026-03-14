from rest_framework import serializers
from .models import Game
from django.contrib.auth.models import User 


class GameSerializer(serializers.ModelSerializer):
    """Full Game serializer for CRUD operations"""
    opponent = serializers.SerializerMethodField()
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    win_method_display = serializers.CharField(source='get_win_method_display', read_only=True)
    
    class Meta:
        model = Game
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'id', 'user']  # Add 'user' here
        extra_kwargs = {
            'user': {'required': False},  # Not required since it's read-only
        }
    
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
    
    def validate_user(self, value):
        """Handle both user ID and user instance"""
        from django.contrib.auth.models import User
        
        # If it's already a User instance, return it
        if isinstance(value, User):
            return value
        
        # If it's an integer, try to get the User instance
        if isinstance(value, int):
            try:
                return User.objects.get(id=value)
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with id {value} does not exist")
        
        # If it's a string that can be converted to int
        if isinstance(value, str) and value.isdigit():
            try:
                return User.objects.get(id=int(value))
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with id {value} does not exist")
        
        raise serializers.ValidationError(f"Invalid user value: {value}")
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
        fields = '__all__'
        extra_kwargs = {
            'user': {'required': True, 'allow_null': False},
        }
    
    def validate_user(self, value):
        """Validate that user ID exists"""
        
        # If it's already a User instance, return it
        if isinstance(value, User):
            return value
        
        # If it's an integer or string that can be converted to int
        try:
            # Try to convert to int if it's a string
            if isinstance(value, str):
                value = int(value)
            
            user = User.objects.get(id=value)
            return user
        except (ValueError, TypeError) as e:
            raise serializers.ValidationError(f"Invalid user ID: {value}")
        except User.DoesNotExist:
            raise serializers.ValidationError(f"User with id {value} does not exist")
    
    def create(self, validated_data):
        return super().create(validated_data)
    
    def validate(self, data):
        return data

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