import re
import csv
from datetime import datetime
import chess.pgn
import io

class ChessComImporter:
    """Import games from Chess.com CSV export"""
    
    RESULT_MAP = {
        'win': 'W',
        'checkmated': 'L',
        'stalemate': 'D',
        'timeout': 'L',
        'resigned': 'L',  # Default, will be adjusted based on context
        'abandoned': 'L',  # Default, will be adjusted based on context
        'repetition': 'D',
        'insufficient': 'D',
        'timevsinsufficient': 'D',
        'agreed': 'D',
    }
    
    WIN_METHOD_MAP = {
        'resigned': 'RES',
        'checkmate': 'CHM',
        'timeout': 'TIM',
        'abandoned': 'ABD',
        'stalemate': 'STM',
        'repetition': 'REP',
        'insufficient': 'INS',
        'timevsinsufficient': 'TVI',
        'agreed': 'AGR',
    }
    
    @classmethod
    def parse_date(cls, date_str):
        """Parse Chess.com date format ' 2018.04.06'"""
        if not date_str or date_str.strip() == '':
            return None
        try:
            return datetime.strptime(date_str.strip(), '%Y.%m.%d').date()
        except ValueError:
            return None
    
    @classmethod
    def parse_time(cls, time_str):
        """Parse Chess.com time format '01:47:32'"""
        if not time_str or time_str.strip() == '':
            return None
        try:
            return datetime.strptime(time_str.strip(), '%H:%M:%S').time()
        except ValueError:
            return None
    
    @classmethod
    def parse_row(cls, row):
        """Parse a single CSV row into Game model data"""
        
        # Get basic info
        game_result = row.get('result', '').lower()
        won_by = row.get('wonBy', '').lower() if row.get('wonBy') else ''
        outcome = row.get('outcome', '').lower() if row.get('outcome') else ''
        user_color = row.get('userColor', '').lower()
        
        # Determine result and win method
        if game_result == 'win':
            result_code = 'W'
            win_method = cls.WIN_METHOD_MAP.get(won_by if won_by else outcome, 'OTH')
        elif game_result == 'checkmated':
            result_code = 'L'
            win_method = cls.WIN_METHOD_MAP.get('checkmate', 'CHM')
        elif game_result in ['stalemate', 'repetition', 'insufficient', 'agreed', 'timevsinsufficient']:
            result_code = 'D'
            win_method = cls.WIN_METHOD_MAP.get(game_result, 'OTH')
        elif game_result in ['resigned', 'timeout', 'abandoned']:
            # For these, the result column tells us who won
            # If userColor is white and result is 'resigned', that means opponent resigned -> win for user
            if user_color == 'white' and game_result == 'resigned':
                result_code = 'W'
            elif user_color == 'black' and game_result == 'resigned':
                result_code = 'W'
            else:
                result_code = 'L'
            win_method = cls.WIN_METHOD_MAP.get(game_result, 'OTH')
        else:
            result_code = None
            win_method = None
        
        # Parse players
        white_player = row.get('userName', '') if user_color == 'white' else row.get('opponent', '')
        black_player = row.get('opponent', '') if user_color == 'white' else row.get('userName', '')
        
        # Get ratings
        my_rating = cls.parse_int(row.get('userRating'))
        opponent_rating = cls.parse_int(row.get('opponentRating'))
        
        # Determine my_color
        my_color = 'white' if user_color == 'white' else 'black'
        
        # Parse date and times
        date_played = cls.parse_date(row.get('date', ''))
        start_time = cls.parse_time(row.get('startTime', ''))
        end_time = cls.parse_time(row.get('endTime', ''))
        
        # Build game data
        game_data = {
            'platform': 'CH',  # Chess.com
            'game_id': row.get('gameId', '').strip(),
            'game_url': row.get('gameUrl', '').strip(),
            'date_played': date_played or datetime.now().date(),
            'start_time': start_time,
            'end_time': end_time,
            'time_class': row.get('timeClass', '').lower(),
            'time_control': '',
            'white_player': white_player or 'Unknown',
            'black_player': black_player or 'Unknown',
            'my_color': my_color,
            'result': result_code,
            'win_method': win_method,
            'outcome': outcome,
            'termination': won_by or outcome,
            'my_rating': my_rating,
            'opponent_rating': opponent_rating,
            'opponent_name': row.get('opponent', ''),
            'opponent_url': row.get('opponentUrl', ''),
            'opening': row.get('opening', '').strip(),
            'opening_url': row.get('openingUrl', '').strip(),
            'fen': row.get('fen', '').strip(),
            'move_count': cls.parse_int(row.get('moveCount')),
            'my_accuracy': cls.parse_float(row.get('userAccuracy')),
            'opponent_accuracy': cls.parse_float(row.get('opponentAccuracy')),
            'is_active': True,
        }
        
        return game_data
    
    @staticmethod
    def parse_int(value):
        """Parse integer value safely"""
        if not value or str(value).strip() == '' or str(value).strip() == 'null':
            return None
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def parse_float(value):
        """Parse float value safely"""
        if not value or str(value).strip() == '' or str(value).strip() == 'null':
            return None
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return None


class LichessImporter:
    """Import games from Lichess PGN export"""
    
    RESULT_MAP = {
        '1-0': ('W', 'L'),  # (white_result, black_result)
        '0-1': ('L', 'W'),
        '1/2-1/2': ('D', 'D'),
        '*': (None, None),
    }
    
    @classmethod
    def parse_pgn(cls, pgn_content, username=None):
        """Parse PGN content containing multiple games"""
        games = []
        
        # Split by empty lines between games
        pgn_games = pgn_content.strip().split('\n\n\n')
        
        for pgn_game in pgn_games:
            if pgn_game.strip():
                game_data = cls.parse_single_game(pgn_game.strip(), username)
                if game_data:
                    games.append(game_data)
        
        return games
    
    @classmethod
    def parse_single_game(cls, pgn_string, username=None):
        """Parse a single PGN game"""
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_string))
            if not game:
                return None
            
            headers = game.headers
            
            # Extract basic info
            game_id = headers.get('GameId', '')
            if not game_id:
                # Try to extract from Site
                site = headers.get('Site', '')
                if site:
                    game_id = site.split('/')[-1]
            
            # Parse date
            date_str = headers.get('UTCDate', headers.get('Date', ''))
            date_played = None
            if date_str and '.' in date_str:
                try:
                    date_played = datetime.strptime(date_str, '%Y.%m.%d').date()
                except ValueError:
                    try:
                        date_played = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass
            
            # Parse time
            time_str = headers.get('UTCTime', '')
            utc_time = None
            if time_str and ':' in time_str:
                try:
                    utc_time = datetime.strptime(time_str, '%H:%M:%S').time()
                except ValueError:
                    pass
            
            # Get players
            white = headers.get('White', 'Unknown')
            black = headers.get('Black', 'Unknown')
            
            # Get ratings
            white_elo = cls.parse_int(headers.get('WhiteElo'))
            black_elo = cls.parse_int(headers.get('BlackElo'))
            
            # Get result
            result_str = headers.get('Result', '*')
            white_result, black_result = cls.RESULT_MAP.get(result_str, (None, None))
            
            # Determine which side is the user (if username provided)
            my_color = None
            my_rating = None
            opponent_rating = None
            opponent_name = None
            
            if username:
                if username.lower() == white.lower():
                    my_color = 'white'
                    my_rating = white_elo
                    opponent_rating = black_elo
                    opponent_name = black
                elif username.lower() == black.lower():
                    my_color = 'black'
                    my_rating = black_elo
                    opponent_rating = white_elo
                    opponent_name = white
            
            # Time control
            time_control = headers.get('TimeControl', '')
            
            # Parse time control into time_class
            time_class = 'classical'
            if '+' in time_control:
                time_sec = int(time_control.split('+')[0])
                if time_sec < 180:
                    time_class = 'bullet'
                elif time_sec < 480:
                    time_class = 'blitz'
                elif time_sec < 1500:
                    time_class = 'rapid'
                else:
                    time_class = 'classical'
            
            # Opening
            eco = headers.get('ECO', '')
            opening = headers.get('Opening', '')
            
            # Termination
            termination = headers.get('Termination', '')
            
            # Variant
            variant = headers.get('Variant', 'Standard')
            
            # Parse moves count
            move_count = 0
            node = game
            while node.variations:
                node = node.variations[0]
                move_count += 1
            
            # Get final FEN
            final_node = node
            fen = final_node.board().fen() if final_node else ''
            
            # Full PGN
            full_pgn = str(game)
            
            # Build game data
            game_data = {
                'platform': 'LI',  # Lichess
                'game_id': game_id,
                'game_url': site,
                'date_played': date_played or datetime.now().date(),
                'utc_date': date_played,
                'utc_time': utc_time,
                'time_class': time_class,
                'time_control': time_control,
                'white_player': white,
                'black_player': black,
                'my_color': my_color,
                'result': white_result if my_color == 'white' else black_result,
                'termination': termination,
                'variant': variant,
                'my_rating': my_rating,
                'opponent_rating': opponent_rating,
                'opponent_name': opponent_name,
                'eco': eco,
                'opening': opening,
                'fen': fen,
                'pgn': full_pgn,
                'move_count': move_count // 2,  # Convert half-moves to full moves
                'is_active': True,
            }
            
            return game_data
            
        except Exception as e:
            print(f"Error parsing PGN: {e}")
            return None
    
    @staticmethod
    def parse_int(value):
        """Parse integer value safely"""
        if not value or str(value).strip() == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None