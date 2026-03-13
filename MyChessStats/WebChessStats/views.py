from django.db import models
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Game
from .serializers import (
    GameSerializer, GameListSerializer, 
    GameCreateSerializer, GameImportSerializer
)
from .importers import ChessComImporter, LichessImporter
import json
import csv
import io
import logging

logger = logging.getLogger(__name__)

# ============ AUTHENTICATION VIEWS ============
@require_http_methods(["GET", "POST"])
@ensure_csrf_cookie
def login_view(request):
    """Handle user login - supports both AJAX and regular form submissions"""
    
    # Debug logging
    logger.info("=" * 50)
    logger.info("LOGIN VIEW CALLED")
    logger.info(f"Method: {request.method}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"X-Requested-With: {request.headers.get('X-Requested-With', 'Not present')}")
    logger.info(f"Is AJAX: {request.headers.get('X-Requested-With') == 'XMLHttpRequest'}")
    
    # Check for AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # If user is already authenticated
    if request.user.is_authenticated:
        logger.info(f"User already authenticated: {request.user.username}")
        if is_ajax:
            return JsonResponse({'success': True, 'redirect': '/', 'message': 'Already logged in'})
        return redirect('home')
    
    # Handle POST requests
    if request.method == 'POST':
        logger.info("Processing POST request")
        
        # Handle AJAX JSON requests
        if is_ajax:
            logger.info("Handling as AJAX JSON request")
            try:
                data = json.loads(request.body)
                username = data.get('username')
                password = data.get('password')
                logger.info(f"JSON data received - Username: {username}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON data'
                }, status=400)
        else:
            # Handle regular form submission
            logger.info("Handling as regular form submission")
            username = request.POST.get('username')
            password = request.POST.get('password')
            logger.info(f"Form data received - Username: {username}")
        
        # Validate input
        if not username or not password:
            logger.warning("Missing username or password")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Username and password are required'
                }, status=400)
            else:
                messages.error(request, 'Username and password are required')
                return render(request, 'WebChessStats/login.html')
        
        # Authenticate user
        logger.info(f"Attempting to authenticate user: {username}")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            logger.info(f"Login successful for: {user.username}")
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'redirect': '/',
                    'message': 'Login successful'
                })
            else:
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('home')
        else:
            logger.warning(f"Login failed for username: {username}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid username or password'
                }, status=400)
            else:
                messages.error(request, 'Invalid username or password')
                return render(request, 'WebChessStats/login.html')
    
    # GET request - show login page
    logger.info("Rendering login page (GET request)")
    return render(request, 'WebChessStats/login.html')


def logout_view(request):
    """Handle user logout"""
    logout(request)
    return redirect('login')


# ============ PROTECTED VIEWS ============
@login_required
def home_view(request):
    """Home page view"""
    return render(request, 'WebChessStats/home.html')


@login_required
def game_list_view(request):
    """Games list page view"""
    return render(request, 'WebChessStats/game_list.html')


@login_required
def game_detail_view(request, game_id):
    """Game detail page view"""
    return render(request, 'WebChessStats/game_detail.html', {'game_id': game_id})





@login_required
def import_view(request):
    """Import games page view"""
    return render(request, 'WebChessStats/import.html')


@login_required
def stats_view(request):
    """Statistics page view"""
    return render(request, 'WebChessStats/stats.html')

@login_required
@require_http_methods(["DELETE"])
@csrf_protect
def delete_all_games_direct(request):
    """Direct view to delete ALL games - bypasses DRF completely"""
    if request.method == 'DELETE':
        confirm = request.GET.get('confirm', 'false').lower() == 'true'
        
        total_count = Game.objects.all().count()
        
        if not confirm:
            return JsonResponse({
                'error': 'Confirmation required',
                'message': f'This will delete {total_count} games. Use ?confirm=true to proceed.',
                'total_count': total_count
            }, status=400)
        
        # Delete all games
        deleted_count = Game.objects.all().delete()[0]
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {deleted_count} games',
            'deleted_count': deleted_count
        })
# ============ API VIEWSET ============
class GameViewSet(viewsets.ModelViewSet):
    """
    ViewSet providing CRUD operations for Chess games.
    Requires authentication for all operations.
    """
    def get_serializer_class(self):
        if self.action == 'list':
            return GameListSerializer
        elif self.action == 'create':
            return GameCreateSerializer
        elif self.action == 'import_games':
            return GameImportSerializer
        return GameSerializer
    
    def get_queryset(self):
        queryset = Game.objects.all()
        
        # Filter out soft-deleted by default
        show_deleted = self.request.query_params.get('show_deleted', 'false').lower() == 'true'
        if not show_deleted:
            queryset = queryset.filter(is_active=True)
        
        # Apply filters
        platform = self.request.query_params.get('platform')
        if platform:
            platform_code = 'CH' if platform.lower() == 'chesscom' else 'LI' if platform.lower() == 'lichess' else None
            if platform_code:
                queryset = queryset.filter(platform=platform_code)
        
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(date_played__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_played__lte=date_to)
        
        result = self.request.query_params.get('result')
        if result:
            queryset = queryset.filter(result=result.upper())
        
        time_class = self.request.query_params.get('time_class')
        if time_class:
            queryset = queryset.filter(time_class=time_class.lower())
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(opponent_name__icontains=search) |
                models.Q(white_player__icontains=search) |
                models.Q(black_player__icontains=search)
            )
        
        # Handle sorting
        order_by = self.request.query_params.get('order_by', '-date_played')
        valid_sort_fields = ['date_played', 'my_rating', 'move_count', 'opponent_rating']
        
        # Check if it's a valid field (with or without - prefix)
        field = order_by.lstrip('-')
        if field in valid_sort_fields:
            queryset = queryset.order_by(order_by)
        else:
            # Default sort
            queryset = queryset.order_by('-date_played')
        
        return queryset
    
    @action(detail=False, methods=['post'], url_path='import')
    def import_games(self, request):
        """Bulk import games from Chess.com CSV or Lichess PGN"""
        logger.info(f"Import games endpoint called by user: {request.user.username}")
        
        serializer = GameImportSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"Import serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        platform = serializer.validated_data['platform']
        file = serializer.validated_data['file']
        
        # Get username for both platforms
        username = serializer.validated_data.get('username', request.user.username)
        
        try:
            if platform == 'chesscom':
                # Read CSV file
                decoded_file = file.read().decode('utf-8-sig')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                
                imported = []
                errors = []
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        clean_row = {k: v for k, v in row.items() if k and k.strip()}
                        # Pass the username to the parser
                        game_data = ChessComImporter.parse_row(clean_row, username=username)
                        
                        if game_data and game_data.get('result'):
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
                                    'data': clean_row
                                })
                        else:
                            errors.append({
                                'row': row_num,
                                'error': 'Could not determine game result'
                            })
                    except Exception as e:
                        errors.append({'row': row_num, 'error': str(e)})
                
                return Response({
                    'imported_count': len(imported),
                    'imported': imported,
                    'errors': errors
                }, status=status.HTTP_201_CREATED if imported else status.HTTP_400_BAD_REQUEST)
            
            else:  # lichess
                pgn_content = file.read().decode('utf-8')
                # Use the provided username to identify games
                games = LichessImporter.parse_pgn(pgn_content, username=username)
                
                logger.info(f"Parsed {len(games)} games from Lichess PGN for user {username}")
                
                imported = []
                errors = []
                
                for idx, game_data in enumerate(games):
                    if game_data and game_data.get('result'):
                        game_serializer = GameCreateSerializer(data=game_data)
                        if game_serializer.is_valid():
                            game = game_serializer.save()
                            imported.append({
                                'id': game.id,
                                'game_id': game.game_id,
                                'opponent': game.opponent_name
                            })
                        else:
                            logger.error(f"Game {idx} validation errors: {game_serializer.errors}")
                            errors.append({
                                'game_index': idx,
                                'errors': game_serializer.errors
                            })
                    else:
                        logger.warning(f"Game {idx} could not be parsed or result not determined")
                        errors.append({
                            'game_index': idx,
                            'error': 'Could not determine game result or identify your games'
                        })
                
                return Response({
                    'imported_count': len(imported),
                    'imported': imported,
                    'errors': errors
                }, status=status.HTTP_201_CREATED if imported else status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.exception("Import failed with exception")
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """Get aggregated statistics"""
        queryset = self.get_queryset()
        
        total_games = queryset.count()
        wins = queryset.filter(result=Game.Result.WIN).count()
        losses = queryset.filter(result=Game.Result.LOSS).count()
        draws = queryset.filter(result=Game.Result.DRAW).count()
        
        win_pct = (wins / total_games * 100) if total_games > 0 else 0
        
        return Response({
            'total_games': total_games,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_percentage': round(win_pct, 2),
        })
    
    @action(detail=True, methods=['get'], url_path='pgn')
    def get_pgn(self, request, pk=None):
        """Get PGN format of the game or generate from FEN"""
        game = self.get_object()
        
        response_data = {
            'game_id': game.id,
            'platform': game.get_platform_display(),
            'has_pgn': bool(game.pgn),
            'has_fen': bool(game.fen),
            'fen': game.fen or None,
        }
        
        # If PGN exists, return it
        if game.pgn:
            response_data['pgn'] = game.pgn
            return Response(response_data)
        
        # If only FEN exists, return that info
        if game.fen:
            return Response(response_data)
        
        # No game data available
        return Response({
            'error': 'No PGN or FEN available for this game',
            'game_id': game.id
        }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['delete'], url_path='delete-all')
    def delete_all_games(self, request):
        """Delete ALL games permanently - bypasses soft delete and pagination"""
        # Use the actual model manager, not the viewset's filtered queryset
        total_count = Game.objects.all().count()
        active_count = Game.objects.filter(is_active=True).count()
        
        # Optional: Add a confirmation parameter
        confirm = request.query_params.get('confirm', 'false').lower() == 'true'
        
        if not confirm:
            return Response({
                'error': 'Confirmation required',
                'message': f'This will delete {total_count} total games ({active_count} active). Use ?confirm=true to proceed.',
                'total_count': total_count,
                'active_count': active_count
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Hard delete ALL games - completely bypass the model's default manager
        # This deletes every single game record from the database
        deleted_count = Game.objects.all().delete()[0]
        
        return Response({
            'success': True,
            'message': f'Successfully deleted {deleted_count} games',
            'deleted_count': deleted_count
        })

    
from .board_utils import fen_to_svg, get_last_move_from_moves

@login_required
def game_board_view(request, game_id):
    """Return board image for a game"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        game = Game.objects.get(id=game_id, is_active=True)
        logger.info(f"Generating board for game {game_id}")
        
        # Try to get FEN from game
        fen = game.fen
        
        # If no FEN but we have PGN, try to extract final position
        if not fen and game.pgn:
            try:
                import chess.pgn
                from io import StringIO
                pgn_game = chess.pgn.read_game(StringIO(game.pgn))
                if pgn_game:
                    board = pgn_game.board()
                    for move in pgn_game.mainline_moves():
                        board.push(move)
                    fen = board.fen()
                    logger.info(f"Generated FEN from PGN: {fen[:50]}...")
            except Exception as e:
                logger.error(f"Error parsing PGN for board: {e}")
        
        if fen:
            from .board_utils import fen_to_svg
            svg_data = fen_to_svg(fen)
            if svg_data:
                return JsonResponse({
                    'success': True,
                    'image': svg_data,
                    'fen': fen
                })
            else:
                logger.error(f"Failed to generate SVG from FEN: {fen}")
        
        return JsonResponse({
            'success': False,
            'error': 'Could not generate board image'
        })
        
    except Game.DoesNotExist:
        logger.error(f"Game {game_id} not found")
        return JsonResponse({
            'success': False,
            'error': 'Game not found'
        }, status=404)
    except Exception as e:
        logger.exception(f"Unexpected error generating board: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)