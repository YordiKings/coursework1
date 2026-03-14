from django.db import models
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
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
@require_http_methods(["GET", "POST"])
@ensure_csrf_cookie
def register_view(request):
    """Handle user registration - supports both AJAX and regular form submissions"""
    
    logger.info("=" * 50)
    logger.info("REGISTER VIEW CALLED")
    logger.info(f"Method: {request.method}")
    
    # If user is already authenticated
    if request.user.is_authenticated:
        logger.info(f"User already authenticated: {request.user.username}")
        return redirect('home')
    
    # Check for AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Handle POST requests
    if request.method == 'POST':
        logger.info("Processing registration POST request")
        
        # Handle AJAX JSON requests
        if is_ajax:
            try:
                data = json.loads(request.body)
                username = data.get('username')
                email = data.get('email', '')
                password = data.get('password')
                password_confirm = data.get('password_confirm')
                logger.info(f"JSON data received - Username: {username}, Email: {email}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON data'
                }, status=400)
        else:
            # Handle regular form submission
            username = request.POST.get('username')
            email = request.POST.get('email', '')
            password = request.POST.get('password')
            password_confirm = request.POST.get('password_confirm')
        
        # Validate input
        errors = {}
        
        if not username:
            errors['username'] = 'Username is required'
        elif len(username) < 3:
            errors['username'] = 'Username must be at least 3 characters'
        elif User.objects.filter(username=username).exists():
            errors['username'] = 'Username already taken'
        
        if email and User.objects.filter(email=email).exclude(email='').exists():
            errors['email'] = 'Email already registered'
        
        if not password:
            errors['password'] = 'Password is required'
        elif len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters'
        
        if password != password_confirm:
            errors['password_confirm'] = 'Passwords do not match'
        
        # Validate password strength using Django's validators
        if password and not errors.get('password'):
            try:
                validate_password(password)
            except ValidationError as e:
                errors['password'] = ', '.join(e.messages)
        
        if errors:
            logger.warning(f"Registration validation errors: {errors}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
            else:
                for field, error in errors.items():
                    messages.error(request, f"{field}: {error}")
                return render(request, 'WebChessStats/register.html')
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            logger.info(f"User created successfully: {username}")
            
            # Log the user in
            login(request, user)
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'redirect': '/',
                    'message': 'Registration successful! Welcome aboard!'
                })
            else:
                messages.success(request, f'Welcome, {username}! Your account has been created.')
                return redirect('home')
                
        except Exception as e:
            logger.exception(f"Error creating user: {e}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'An error occurred during registration. Please try again.'
                }, status=500)
            else:
                messages.error(request, 'An error occurred during registration. Please try again.')
                return render(request, 'WebChessStats/register.html')
    
    # GET request - show registration page
    logger.info("Rendering registration page (GET request)")
    return render(request, 'WebChessStats/register.html')

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
    """Direct view to delete ALL games for the current user"""
    if request.method == 'DELETE':
        confirm = request.GET.get('confirm', 'false').lower() == 'true'
        
        total_count = Game.objects.filter(user=request.user).count()
        
        if not confirm:
            return JsonResponse({
                'error': 'Confirmation required',
                'message': f'This will delete {total_count} games. Use ?confirm=true to proceed.',
                'total_count': total_count
            }, status=400)
        
        # Delete only this user's games
        deleted_count = Game.objects.filter(user=request.user).delete()[0]
        
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
        # Filter by the current user
        queryset = Game.objects.filter(user=self.request.user)
        
        # Filter out soft-deleted by default
        show_deleted = self.request.query_params.get('show_deleted', 'false').lower() == 'true'
        if not show_deleted:
            queryset = queryset.filter(is_active=True)
        
        # Apply other filters (platform, date, etc.)
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
        
        field = order_by.lstrip('-')
        if field in valid_sort_fields:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('-date_played')
        
        return queryset
    
    def perform_create(self, serializer):
        """Set the user when creating a new game manually"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'], url_path='import')
    def import_games(self, request):
        """Bulk import games from Chess.com CSV or Lichess PGN"""
        
        # Log the start of import
        logger.info("=" * 60)
        logger.info("IMPORT GAMES FUNCTION CALLED")
        logger.info("=" * 60)
        logger.info(f"User: {request.user.username} (ID: {request.user.id})")
        logger.info(f"Is authenticated: {request.user.is_authenticated}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Content type: {request.content_type}")
        
        serializer = GameImportSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        platform = serializer.validated_data['platform']
        file = serializer.validated_data['file']
        username = serializer.validated_data.get('username', request.user.username)
        
        logger.info(f"Platform: {platform}")
        logger.info(f"Username provided: {username}")
        logger.info(f"File name: {file.name}")
        logger.info(f"File size: {file.size} bytes")
        
        try:
            if platform == 'chesscom':
                # Read CSV file
                logger.info("Processing Chess.com CSV import...")
                decoded_file = file.read().decode('utf-8-sig')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                
                # Log CSV structure
                logger.info(f"CSV fieldnames: {reader.fieldnames}")
                
                imported = []
                errors = []
                row_count = 0
                games_with_user_set = 0
                
                for row_num, row in enumerate(reader, start=2):
                    row_count += 1
                    
                    # Log every 100 rows to avoid log spam
                    #if row_count % 100 == 0:
                        #logger.info(f"Processed {row_count} rows...")
                    
                    try:
                        clean_row = {k: v for k, v in row.items() if k and k.strip()}
                        
                        # Log first row as sample
                        if row_count == 1:
                            logger.info(f"Sample row data (first row): {clean_row}")
                        
                        game_data = ChessComImporter.parse_row(clean_row, username=username)
                        
                        if game_data and game_data.get('result'):
                            # CRITICAL: Add the current user to game data
                            game_data['user'] = request.user.id
                            games_with_user_set += 1
                            
                            # Log user assignment for first few games
                            if row_count <= 5:
                                logger.info(f"Row {row_count}: Setting user_id={request.user.id} for game {game_data.get('game_id')}")
                                logger.debug(f"Game data keys for row {row_count}: {list(game_data.keys())}")
                            
                            game_serializer = GameCreateSerializer(data=game_data, context={'request': request})
                            if game_serializer.is_valid():
                                game = game_serializer.save()
                                
                                # Log success for first few games
                                #if len(imported) < 10:
                                   # logger.info(f"✓ Row {row_count}: Game saved - ID: {game.id}, User ID in DB: {game.user_id}")
                                
                                imported.append({
                                    'id': game.id,
                                    'game_id': game.game_id,
                                    'opponent': game.opponent_name
                                })
                            else:
                               # logger.error(f"Validation error row {row_num}: {game_serializer.errors}")
                                errors.append({
                                    'row': row_num,
                                    'errors': game_serializer.errors,
                                    'data': clean_row
                                })
                        else:
                           # logger.warning(f"Row {row_num}: Could not determine result. Result field: {clean_row.get('result', 'N/A')}")
                            errors.append({
                                'row': row_num,
                                'error': 'Could not determine game result',
                                'data': clean_row
                            })
                    except Exception as e:
                        logger.exception(f"Exception processing row {row_num}")
                        errors.append({'row': row_num, 'error': str(e)})
                
                # Log summary
                logger.info("=" * 40)
                logger.info("CHESS.COM IMPORT SUMMARY")
                logger.info("=" * 40)
                logger.info(f"Total rows processed: {row_count}")
                logger.info(f"Games where user was set in code: {games_with_user_set}")
                logger.info(f"Successfully imported: {len(imported)}")
                logger.info(f"Errors: {len(errors)}")
                
                # Verify user assignment in database
                if imported:
                    logger.info("Verifying user assignment in database...")
                    sample_size = min(10, len(imported))
                    sample_games = Game.objects.filter(id__in=[g['id'] for g in imported[:sample_size]])
                    null_user_count = 0
                    for game in sample_games:
                        logger.info(f"Verification - Game {game.id}: user_id = {game.user_id} (username: {game.user.username if game.user else 'NO USER'})")
                        if game.user_id is None:
                            null_user_count += 1
                    
                    if null_user_count > 0:
                        logger.error(f"WARNING: {null_user_count} out of {sample_size} sampled games have NULL user!")
                    else:
                        logger.info(f"SUCCESS: All {sample_size} sampled games have proper user assignment")
                
                return Response({
                    'imported_count': len(imported),
                    'imported': imported,
                    'errors': errors
                }, status=status.HTTP_201_CREATED if imported else status.HTTP_400_BAD_REQUEST)
            
            else:  # lichess
                logger.info("Processing Lichess PGN import...")
                pgn_content = file.read().decode('utf-8')
                logger.info(f"PGN content length: {len(pgn_content)} characters")
                logger.info(f"PGN preview (first 500 chars): {pgn_content[:500]}")
                
                games = LichessImporter.parse_pgn(pgn_content, username=username)
                logger.info(f"Parsed {len(games)} games from PGN")
                
                imported = []
                errors = []
                games_with_user_set = 0
                
                for idx, game_data in enumerate(games):
                    if game_data and game_data.get('result'):
                        # CRITICAL: Add the current user to game data
                        game_data['user'] = request.user.id
                        games_with_user_set += 1
                        
                        # Log first few game details
                        if idx < 5:
                            logger.info(f"Game {idx}: Setting user_id={request.user.id}")
                            logger.info(f"Game {idx} details: ID={game_data.get('game_id')}, White={game_data.get('white_player')}, Black={game_data.get('black_player')}, Result={game_data.get('result')}")
                        
                        game_serializer = GameCreateSerializer(data=game_data)
                        if game_serializer.is_valid():
                            game = game_serializer.save()
                            
                            # Log success for first few games
                            if len(imported) < 10:
                                logger.info(f"✓ Game {idx}: Saved - ID: {game.id}, User ID in DB: {game.user_id}")
                            
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
                        logger.warning(f"Game {idx}: Could not parse or determine result")
                        errors.append({
                            'game_index': idx,
                            'error': 'Could not determine game result or identify your games'
                        })
                
                # Log summary
                logger.info("=" * 40)
                logger.info("LICHESS IMPORT SUMMARY")
                logger.info("=" * 40)
                logger.info(f"Games parsed from PGN: {len(games)}")
                logger.info(f"Games where user was set in code: {games_with_user_set}")
                logger.info(f"Successfully imported: {len(imported)}")
                logger.info(f"Errors: {len(errors)}")
                
                # Verify user assignment in database
                if imported:
                    logger.info("Verifying user assignment in database...")
                    sample_size = min(10, len(imported))
                    sample_games = Game.objects.filter(id__in=[g['id'] for g in imported[:sample_size]])
                    null_user_count = 0
                    for game in sample_games:
                        logger.info(f"Verification - Game {game.id}: user_id = {game.user_id} (username: {game.user.username if game.user else 'NO USER'})")
                        if game.user_id is None:
                            null_user_count += 1
                    
                    if null_user_count > 0:
                        logger.error(f"WARNING: {null_user_count} out of {sample_size} sampled games have NULL user!")
                    else:
                        logger.info(f"SUCCESS: All {sample_size} sampled games have proper user assignment")
                
                return Response({
                    'imported_count': len(imported),
                    'imported': imported,
                    'errors': errors
                }, status=status.HTTP_201_CREATED if imported else status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.exception("Fatal error during import")
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """Get aggregated statistics for the current user's games"""
        # Filter by current user
        all_games = Game.objects.filter(user=request.user, is_active=True)
        
        # Basic counts
        total_games = all_games.count()
        wins = all_games.filter(result=Game.Result.WIN).count()
        losses = all_games.filter(result=Game.Result.LOSS).count()
        draws = all_games.filter(result=Game.Result.DRAW).count()
        
        # Win percentage
        win_pct = (wins / total_games * 100) if total_games > 0 else 0
        
        # Statistics by platform
        platform_stats = []
        chesscom_rating_data = []
        lichess_rating_data = []
        
        for platform_code, platform_name in Game.Platform.choices:
            platform_qs = all_games.filter(platform=platform_code)
            count = platform_qs.count()
            if count > 0:
                platform_stats.append({
                    'platform': platform_name,
                    'code': platform_code,
                    'count': count,
                    'wins': platform_qs.filter(result=Game.Result.WIN).count(),
                    'avg_rating': platform_qs.filter(my_rating__isnull=False).aggregate(
                        avg=models.Avg('my_rating')
                    )['avg']
                })
                
                # Get rating progression for this platform
                rated_games = platform_qs.filter(
                    my_rating__isnull=False
                ).order_by('date_played', 'id')
                
                # Group by 3-month periods
                rating_data = list(rated_games.values('date_played', 'my_rating'))
                
                from collections import defaultdict
                import datetime
                
                quarterly_ratings = defaultdict(list)
                
                for item in rating_data:
                    if item['date_played']:
                        date = item['date_played']
                        quarter = f"{date.year}-Q{(date.month-1)//3 + 1}"
                        quarterly_ratings[quarter].append({
                            'date': date,
                            'rating': item['my_rating']
                        })
                
                # For each quarter, take the rating from the last game
                platform_progression = []
                for quarter, games in sorted(quarterly_ratings.items()):
                    if games:
                        last_game = sorted(games, key=lambda x: x['date'])[-1]
                        
                        year = int(quarter.split('-')[0])
                        q_num = int(quarter.split('-Q')[1])
                        last_month = q_num * 3
                        
                        display_date = datetime.date(year, last_month, 1)
                        
                        platform_progression.append({
                            'date': display_date.strftime('%Y-%m'),
                            'my_rating': last_game['rating'],
                            'quarter': quarter
                        })
                
                # Store platform-specific data
                if platform_code == 'CH':
                    chesscom_rating_data = platform_progression[-20:]  # Last 20 quarters
                elif platform_code == 'LI':
                    lichess_rating_data = platform_progression[-20:]
        
        # Statistics by time class
        time_stats = []
        for time_class, time_name in Game.TimeClass.choices:
            time_qs = all_games.filter(time_class=time_class)
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
        top_openings = all_games.values('opening').annotate(
            count=models.Count('id'),
            wins=models.Count('id', filter=models.Q(result=Game.Result.WIN))
        ).exclude(opening='').exclude(opening='Undefined').exclude(opening__isnull=True).filter(count__gte=2).order_by('-count')[:15]
        
        for opening in top_openings:
            opening['win_percentage'] = round(
                opening['wins'] / opening['count'] * 100, 2
            ) if opening['count'] > 0 else 0
        
        return Response({
            'total_games': total_games,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_percentage': round(win_pct, 2),
            'by_platform': platform_stats,
            'by_time_class': time_stats,
            'top_openings': list(top_openings),
            'chesscom_rating': chesscom_rating_data,
            'lichess_rating': lichess_rating_data,
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
        """Delete ALL games for the current user"""
        # Only delete games belonging to the current user
        total_count = Game.objects.filter(user=request.user).count()
        active_count = Game.objects.filter(user=request.user, is_active=True).count()
        
        # Optional: Add a confirmation parameter
        confirm = request.query_params.get('confirm', 'false').lower() == 'true'
        
        if not confirm:
            return Response({
                'error': 'Confirmation required',
                'message': f'This will delete {total_count} total games ({active_count} active). Use ?confirm=true to proceed.',
                'total_count': total_count,
                'active_count': active_count
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete only this user's games
        deleted_count = Game.objects.filter(user=request.user).delete()[0]
        
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
    
@action(detail=False, methods=['get'], url_path='debug-counts')
def debug_counts(self, request):
    """Debug endpoint to check actual game counts"""
    all_games = Game.objects.filter(is_active=True)
    
    # Count by result
    wins = all_games.filter(result=Game.Result.WIN).count()
    losses = all_games.filter(result=Game.Result.LOSS).count()
    draws = all_games.filter(result=Game.Result.DRAW).count()
    null_results = all_games.filter(result__isnull=True).count()
    
    # Sample some games to see their result values
    samples = list(all_games.values('id', 'result', 'white_player', 'black_player', 'my_color')[:10])
    
    return Response({
        'total': all_games.count(),
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'null_results': null_results,
        'samples': samples
    })    