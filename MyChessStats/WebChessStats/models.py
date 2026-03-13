from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Game(models.Model):
    # Platform identification
    class Platform(models.TextChoices):
        CHESSCOM = 'CH', 'Chess.com'
        LICHESS = 'LI', 'Lichess'
    
    # Game result choices
    class Result(models.TextChoices):
        WIN = 'W', 'Win'
        LOSS = 'L', 'Loss'
        DRAW = 'D', 'Draw'
    
    # Termination/Win method
    class WinMethod(models.TextChoices):
        RESIGNATION = 'RES', 'Resignation'
        CHECKMATE = 'CHM', 'Checkmate'
        TIMEOUT = 'TIM', 'Timeout'
        ABANDONED = 'ABD', 'Abandoned'
        AGREED = 'AGR', 'Agreed Draw'
        STALEMATE = 'STM', 'Stalemate'
        REPETITION = 'REP', 'Repetition'
        INSUFFICIENT = 'INS', 'Insufficient Material'
        TIME_VS_INSUFFICIENT = 'TVI', 'Time vs Insufficient'
        OTHER = 'OTH', 'Other'
    
    # Time control categories
    class TimeClass(models.TextChoices):
        BULLET = 'bullet', 'Bullet'
        BLITZ = 'blitz', 'Blitz'
        RAPID = 'rapid', 'Rapid'
        CLASSICAL = 'classical', 'Classical'
        CORRESPONDENCE = 'correspondence', 'Correspondence'
    
    # Basic identifiers
    platform = models.CharField(max_length=2, choices=Platform.choices, db_index=True)
    game_id = models.CharField(max_length=100, unique=True, db_index=True)
    game_url = models.URLField(max_length=500, blank=True)
    
    # Date and time
    date_played = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    utc_date = models.DateField(null=True, blank=True)
    utc_time = models.TimeField(null=True, blank=True)
    
    # Game classification
    time_class = models.CharField(max_length=20, choices=TimeClass.choices, db_index=True)
    time_control = models.CharField(max_length=20, blank=True)
    
    # Players
    white_player = models.CharField(max_length=100, db_index=True)
    black_player = models.CharField(max_length=100, db_index=True)
    my_color = models.CharField(max_length=5, choices=[('white', 'White'), ('black', 'Black')])
    
    # Results
    result = models.CharField(max_length=1, choices=Result.choices, db_index=True)
    termination = models.CharField(max_length=50, blank=True)
    win_method = models.CharField(max_length=3, choices=WinMethod.choices, null=True, blank=True)
    outcome = models.CharField(max_length=50, blank=True)
    
    # Ratings
    my_rating = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(3500)],
        null=True, blank=True,
        db_index=True
    )
    opponent_rating = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(3500)],
        null=True, blank=True
    )
    opponent_name = models.CharField(max_length=100, blank=True)
    opponent_url = models.URLField(max_length=500, blank=True)
    rating_change = models.IntegerField(null=True, blank=True)
    
    # Opening information
    eco = models.CharField(max_length=3, blank=True)
    opening = models.CharField(max_length=200, blank=True, db_index=True)
    opening_url = models.URLField(max_length=500, blank=True)
    
    # Game data
    fen = models.CharField(max_length=100, blank=True)
    pgn = models.TextField(blank=True)
    moves = models.TextField(blank=True)
    move_count = models.IntegerField(default=0)
    
    # Accuracy metrics
    my_accuracy = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    opponent_accuracy = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Additional Lichess-specific fields
    variant = models.CharField(max_length=50, blank=True)
    
    # Parsed move data (store as JSON for flexibility)
    moves_with_eval = models.JSONField(default=list, blank=True)
    
    # CRUD tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-date_played', '-start_time']
        indexes = [
            models.Index(fields=['platform', 'date_played']),
            models.Index(fields=['result', 'my_color']),
            models.Index(fields=['opening']),
            models.Index(fields=['time_class']),
            models.Index(fields=['my_rating']),
            models.Index(fields=['opponent_name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"Game {self.id}: {self.white_player} vs {self.black_player} ({self.date_played})"
    
    def get_opponent(self):
        """Get opponent name based on my_color"""
        if self.my_color == 'white':
            return self.black_player
        return self.white_player
    
    def get_my_rating_change_display(self):
        """Format rating change with + sign"""
        if self.rating_change:
            sign = '+' if self.rating_change > 0 else ''
            return f"{sign}{self.rating_change}"
        return "N/A"
    
    def soft_delete(self):
        """Soft delete instead of actual deletion"""
        self.is_active = False
        self.save()
    
    def restore(self):
        """Restore soft-deleted game"""
        self.is_active = True
        self.save()