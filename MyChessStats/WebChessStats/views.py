from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg, Sum
from .models import Game
from .serializers import (
    GameSerializer, GameListSerializer, 
    GameCreateSerializer, GameImportSerializer,
    GameStatsSerializer
)
from .importers import ChessComImporter, LichessImporter
import csv
import io

class GameViewSet(viewsets.ModelViewSet):
    """
    ViewSet providing CRUD operations for Chess games.
    
    Endpoints:
    - GET /api/games/ - List all games
    - POST /api/games/ - Create new game
    - GET /api/games/{id}/ - Retrieve specific game
    - PUT /api/games/{id}/ - Update game
    - PATCH /api/games/{id}/ - Partial update
    - DELETE /api/games/{id}/ - Delete game
    - POST /api/games/import/ - Bulk import from CSV/PGN
    - GET /api/games/stats/ - Get game statistics
    - POST /api/games/{id}/restore/ - Restore soft-deleted game
    - GET /api/games/{id}/pgn/ - Get PGN format
    """
    
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return GameListSerializer
        elif self.action == 'create':
            return GameCreateSerializer
        elif self.action == 'import_games':
            return GameImportSerializer
        elif self.action == 'statistics':
            return GameStatsSerializer
        return GameSerializer
    
    def get_queryset(self):
        queryset = Game.objects.all()
        
        # Filter out soft-deleted by default
        show_deleted = self.request.query_params.get('show_deleted', 'false').lower() == 'true'
        if not show_deleted:
            queryset = queryset.filter(is_active=True)
        
        # Filter by platform
        platform = self.request.query_params.get('platform')
        if platform:
            platform_code = 'CH' if platform.lower() == 'chesscom' else 'LI' if platform.lower() == 'lichess' else None
            if platform_code:
                queryset = queryset.filter(platform=platform_code)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(date_played__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_played__lte=date_to)
        
        # Filter by result
        result = self.request.query_params.get('result')
        if result:
            result_code = result[0].upper()  # W, L, D
            queryset = queryset.filter(result=result_code)
        
        # Filter by opening
        opening = self.request.query_params.get('opening')
        if opening:
            queryset = queryset.filter(opening__icontains=opening)
        
        # Filter by time class
        time_class = self.request.query_params.get('time_class')
        if time_class:
            queryset = queryset.filter(time_class=time_class.lower())
        
        # Search by opponent
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(opponent_name__icontains=search) |
                Q(white_player__icontains=search) |
                Q(black_player__icontains=search)
            )
        
        # Ordering
        order_by = self.request.query_params.get('order_by', '-date_played')
        if order_by in ['date_played', '-date_played', 'my_rating', '-my_rating', 
                       'move_count', '-move_count', 'created_at', '-created_at']:
            queryset = queryset.order_by(order_by)
        
        return queryset
    
    def destroy(self, request, *args, **kwargs):
        """Override delete to support soft delete"""
        instance = self.get_object()
        
        hard_delete = request.query_params.get('hard', 'false').lower() == 'true'
        
        if hard_delete:
            self.perform_destroy(instance)
            return Response(
                {"message": "Game permanently deleted"},
                status=status.HTTP_204_NO_CONTENT
            )
        else:
            instance.soft_delete()
            return Response(
                {
                    "message": "Game soft deleted",
                    "id": instance.id,
                    "note": "Use ?hard=true to permanently delete, or POST to /restore/ to restore"
                },
                status=status.HTTP_200_OK
            )
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore a soft-deleted game"""
        game = self.get_object()
        if game.is_active:
            return Response(
                {"message": "Game is already active", "id": game.id},
                status=status.HTTP_400_BAD_REQUEST
            )
        game.restore()
        serializer = self.get_serializer(game)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='import')
    def import_games(self, request):
        """Bulk import games from Chess.com CSV or Lichess PGN"""
        serializer = GameImportSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        platform = serializer.validated_data['platform']
        file = serializer.validated_data['file']
        
        try:
            if platform == 'chesscom':
                # Read CSV file
                decoded_file = file.read().decode('utf-8-sig')  # Handle BOM
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                
                imported = []
                errors = []
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        game_data = ChessComImporter.parse_row(row)
                        # Add platform
                        game_data['platform'] = Game.Platform.CHESSCOM
                        
                        game_serializer = GameCreateSerializer(data=game_data)
                        if game_serializer.is_valid():
                            game = game_serializer.save()
                            imported.append({
                                'id': game.id,
                                'game_id': game.game_id,
                                'opponent': game.opponent_name
                            })
                        else:
                            errors.append({
                                'row': row_num,
                                'errors': game_serializer.errors,
                                'data': row
                            })
                    except Exception as e:
                        errors.append({
                            'row': row_num,
                            'error': str(e)
                        })
                
                return Response({
                    'imported_count': len(imported),
                    'imported': imported,
                    'errors': errors
                }, status=status.HTTP_201_CREATED if imported else status.HTTP_400_BAD_REQUEST)
            
            else:  # lichess
                # Parse PGN file
                pgn_content = file.read().decode('utf-8')
                games = LichessImporter.parse_pgn(pgn_content)
                
                imported = []
                errors = []
                
                for idx, game_data in enumerate(games):
                    # Add platform
                    game_data['platform'] = Game.Platform.LICHESS
                    
                    game_serializer = GameCreateSerializer(data=game_data)
                    if game_serializer.is_valid():
                        game = game_serializer.save()
                        imported.append({
                            'id': game.id,
                            'game_id': game.game_id,
                            'opponent': game.opponent_name
                        })
                    else:
                        errors.append({
                            'game_index': idx,
                            'errors': game_serializer.errors
                        })
                
                return Response({
                    'imported_count': len(imported),
                    'imported': imported,
                    'errors': errors
                }, status=status.HTTP_201_CREATED if imported else status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """Get aggregated statistics"""
        queryset = self.get_queryset()
        
        # Basic counts
        total_games = queryset.count()
        wins = queryset.filter(result=Game.Result.WIN).count()
        losses = queryset.filter(result=Game.Result.LOSS).count()
        draws = queryset.filter(result=Game.Result.DRAW).count()
        
        # Win percentage
        win_pct = (wins / total_games * 100) if total_games > 0 else 0
        
        # Statistics by platform
        platform_stats = []
        for platform_code, platform_name in Game.Platform.choices:
            platform_qs = queryset.filter(platform=platform_code)
            count = platform_qs.count()
            if count > 0:
                platform_stats.append({
                    'platform': platform_name,
                    'code': platform_code,
                    'count': count,
                    'wins': platform_qs.filter(result=Game.Result.WIN).count(),
                    'avg_rating': platform_qs.filter(my_rating__isnull=False).aggregate(
                        avg=Avg('my_rating')
                    )['avg']
                })
        
        # Statistics by time class
        time_stats = []
        for time_class, time_name in Game.TimeClass.choices:
            time_qs = queryset.filter(time_class=time_class)
            count = time_qs.count()
            if count > 0:
                time_stats.append({
                    'time_class': time_name,
                    'code': time_class,
                    'count': count,
                    'wins': time_qs.filter(result=Game.Result.WIN).count(),
                    'win_percentage': round(
                        time_qs.filter(result=Game.Result.WIN).count() / count * 100, 2
                    ) if count > 0 else 0
                })
        
        # Statistics by opening (top 15)
        top_openings = queryset.values('opening').annotate(
            count=Count('id'),
            wins=Count('id', filter=Q(result=Game.Result.WIN))
        ).exclude(opening='').exclude(opening='Undefined').filter(count__gte=2).order_by('-count')[:15]
        
        for opening in top_openings:
            opening['win_percentage'] = round(
                opening['wins'] / opening['count'] * 100, 2
            ) if opening['count'] > 0 else 0
        
        # Rating progression (last 50 games)
        rating_progression = list(queryset.filter(
            my_rating__isnull=False
        ).order_by('-date_played')[:50].values('date_played', 'my_rating'))
        rating_progression.reverse()  # Chronological order
        
        # Monthly stats
        monthly_stats = queryset.extra(
            select={'month': "strftime('%%Y-%%m', date_played)"}
        ).values('month').annotate(
            count=Count('id'),
            wins=Count('id', filter=Q(result=Game.Result.WIN))
        ).order_by('month')
        
        for month in monthly_stats:
            month['win_percentage'] = round(
                month['wins'] / month['count'] * 100, 2
            ) if month['count'] > 0 else 0
        
        return Response({
            'total_games': total_games,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_percentage': round(win_pct, 2),
            'by_platform': platform_stats,
            'by_time_class': time_stats,
            'top_openings': list(top_openings),
            'rating_progression': rating_progression,
            'monthly_stats': list(monthly_stats)
        })
    
    @action(detail=True, methods=['get'], url_path='pgn')
    def get_pgn(self, request, pk=None):
        """Get PGN format of the game"""
        game = self.get_object()
        
        if not game.pgn:
            return Response(
                {'error': 'No PGN available for this game'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'pgn': game.pgn,
            'game_id': game.id,
            'platform': game.get_platform_display()
        })
    
    @action(detail=False, methods=['delete'], url_path='purge')
    def purge_all(self, request):
        """Permanently delete all soft-deleted games (admin only)"""
        # In production, add permission check here
        count = Game.objects.filter(is_active=False).delete()[0]
        return Response({
            'message': f'Permanently deleted {count} soft-deleted games'
        })