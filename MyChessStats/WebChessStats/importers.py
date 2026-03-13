import re
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
        'resigned': 'L' if 'win' else 'W',  # Context dependent
        'abandoned': 'L' if 'win' else 'W',  # Context dependent
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
        if not date_str:
            return None
        return datetime.strptime(date_str.strip(), '%Y.%m.%d').date()
    
    @classmethod
    def parse_time(cls, time_str):
        """Parse Chess.com time format '01:47:32'"""
        if not time_str or time_str.strip() == '':
            return None
        return datetime.strptime(time_str.strip(), '%H:%M:%S').time()
    
    @classmethod
    def parse_row(cls, row):
        """Parse a single CSV row into Game model data"""
        
        # Determine result based on 'result' and 'wonBy'
        result = row.get('result', '').lower()
        won_by = row.get('wonBy', '').lower() if row.get('wonBy') else ''
        outcome = row.get('outcome', '').lower() if row.get('outcome') else ''
        
        # Handle result
        if result == 'win':
            game_result = 'W'
            win_method = cls.WIN_METHOD_MAP.get(won_by if won_by else outcome, 'OTH')
        elif result == 'checkmated':
            game_result = 'L'
            win_method = cls.WIN_METHOD_MAP.get('checkmate', 'CHM')
        elif result in ['stalemate', 'repetition', 'insufficient', 'agreed', 'timevsinsufficient']:
            game_result = 'D'
            win_method = cls.WIN_METHOD_MAP.get(result, 'OTH')
        elif result in ['resigned', 'timeout', 'abandoned']:
            # Need to determine if this was a win or loss from context
            # In Chess.com data, 'win' in result column means we won
            game_result = 'W' if row.get('result') == 'win' else 'L'
            win_method = cls.WIN_METHOD_MAP.get(result, 'OTH')
        else:
            game_result = None
            win_method = None
        
        # Parse date
        date_played = cls.parse_date(row.get('date', ''))
        
        # Parse times
        start_time = cls.parse_time(row.get('startTime', ''))
        end_time = cls.parse_time(row.get('endTime', ''))
        
        # Determine my_color
        my_color = row.get('userColor', '').lower()
        
        # Get opponent name
        white_player = row.get('white', 'Unknown')
        black_player = row.get('black', 'Unknown')
        
        # Build game data dictionary
        game_data = {
            'game_id': row.get('gameId', '').strip(),
            'game_url': row.get('gameUrl', '').strip(),
            'date_played': date_played,
            'start_time': start_time,
            'end_time': end_time,
            'time_class': row.get('timeClass', '').lower(),
            'time_control': '',  # Not in CSV
            'white_player': white_player,
            'black_player': black_player,
            'my_color': my_color,
            'result': game_result,
            'win_method': win_method,
            'outcome': row.get('outcome', ''),
            'termination': won_by or outcome,
            'my_rating': cls.parse_int(row.get('userRating')),
            'opponent_rating': cls.parse_int(row.get('opponentRating')),
            'opponent_name': row.get('opponent', ''),
            'opponent_url': row.get('opponentUrl', ''),
            'opening': row.get('opening', '').strip(),
            'opening_url': row.get('openingUrl', '').strip(),
            'fen': row.get('fen', '').strip(),
            'move_count': cls.parse_int(row.get('moveCount')),
            'my_accuracy': cls.parse_float(row.get('userAccuracy')),
            'opponent_accuracy': cls.parse_float(row.get('opponentAccuracy')),
        }
        
        return game_data
    
    @staticmethod
    def parse_int(value):
        """Parse integer value safely"""
        if not value or str(value).strip() == '':
            return None
        try:
            return int(float(value))  # Handle decimal strings
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def parse_float(value):
        """Parse float value safely"""
        if not value or str(value).strip() == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class LichessImporter:
    """Import games from Lichess PGN export"""
    
    RESULT_MAP = {
        '1-0': 'W',  # White wins
        '0-1': 'L',  # Black wins
        '1/2-1/2': 'D',  # Draw
        '*': None,  # Unknown/ongoing
    }
    
    @classmethod
    def parse_pgn(cls, pgn_content):
        """Parse PGN content containing multiple games"""
        games = []
        current_game = []
        
        for line in pgn_content.split('\n'):
            current_game.append(line)
            if line.strip() == '' and len(current_game) > 1 and current_game[-2].strip() != '':
                # Empty line might separate games
                if any('[Event ' in l for l in current_game):
                    game_str = '\n'.join(current_game)
                    game_data = cls.parse_single_game(game_str)
                    if game_data:
                        games.append(game_data)
                current_game = []
        
        # Parse last game
        if current_game and any('[Event ' in l for l in current_game):
            game_str = '\n'.join(current_game)
            game_data = cls.parse_single_game(game_str)
            if game_data:
                games.append(game_data)
        
        return games
    
    @classmethod
    def parse_single_game(cls, pgn_string):
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
            result = cls.RESULT_MAP.get(result_str)
            
            # Time control
            time_control = headers.get('TimeControl', '')
            
            # Opening
            eco = headers.get('ECO', '')
            opening = headers.get('Opening', '')
            
            # Termination
            termination = headers.get('Termination', '')
            
            # Variant
            variant = headers.get('Variant', 'Standard')
            
            # Parse moves
            moves_with_eval = []
            move_count = 0
            node = game
            move_number = 1
            
            while node.variations:
                node = node.variations[0]
                move = node.san()
                
                # Extract evaluation if present
                comment = node.comment
                eval_match = re.search(r'%eval (-?\d+\.?\d*)', comment) if comment else None
                evaluation = float(eval_match.group(1)) if eval_match else None
                
                moves_with_eval.append({
                    'move_number': move_number,
                    'move': move,
                    'evaluation': evaluation,
                    'comment': comment
                })
                move_number += 1
            
            move_count = len(moves_with_eval)
            
            # Get final FEN
            final_node = node
            fen = final_node.board().fen() if final_node else ''
            
            # Full PGN
            full_pgn = str(game)
            
            # Build game data
            game_data = {
                'game_id': game_id,
                'date_played': date_played,
                'utc_date': date_played,
                'utc_time': utc_time,
                'time_control': time_control,
                'white_player': white,
                'black_player': black,
                'result': result,
                'termination': termination,
                'variant': variant,
                'my_rating': None,  # Will be set based on which side you played
                'opponent_rating': None,
                'eco': eco,
                'opening': opening,
                'fen': fen,
                'pgn': full_pgn,
                'moves_with_eval': moves_with_eval,
                'move_count': move_count,
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