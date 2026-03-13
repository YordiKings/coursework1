from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
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

# ============ TEST AJAX VIEW ============
def test_ajax(request):
    """Test endpoint to verify AJAX headers"""
    logger.info("Test AJAX view called")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    return JsonResponse({
        'success': is_ajax,
        'message': 'AJAX is working!' if is_ajax else 'Not an AJAX request',
        'received_header': request.headers.get('X-Requested-With', 'None'),
        'method': request.method
    })

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
def game_create_view(request):
    """Create game page view"""
    if request.method == 'POST':
        messages.success(request, 'Game created successfully!')
        return redirect('game_list')
    return render(request, 'WebChessStats/game_form.html')


@login_required
def import_view(request):
    """Import games page view"""
    return render(request, 'WebChessStats/import.html')


@login_required
def stats_view(request):
    """Statistics page view"""
    return render(request, 'WebChessStats/stats.html')


# ============ API VIEWSET ============
class GameViewSet(viewsets.ModelViewSet):
    """
    ViewSet providing CRUD operations for Chess games.
    Requires authentication for all operations.
    """
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [IsAuthenticated]
    
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
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(opponent_name__icontains=search) |
                models.Q(white_player__icontains=search) |
                models.Q(black_player__icontains=search)
            )
        
        return queryset
    
    @action(detail=False, methods=['post'], url_path='import')
    def import_games(self, request):
        """Bulk import games from Chess.com CSV or Lichess PGN"""
        logger.info("Import games endpoint called")
        
        serializer = GameImportSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"Import serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        platform = serializer.validated_data['platform']
        file = serializer.validated_data['file']
        
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
                        game_data = ChessComImporter.parse_row(clean_row)
                        
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
                games = LichessImporter.parse_pgn(pgn_content, username=request.user.username)
                
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
                            errors.append({
                                'game_index': idx,
                                'errors': game_serializer.errors
                            })
                    else:
                        errors.append({
                            'game_index': idx,
                            'error': 'Could not determine game result'
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