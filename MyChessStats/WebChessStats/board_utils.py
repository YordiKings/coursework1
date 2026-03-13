import chess
import chess.svg
import base64
import logging
from io import BytesIO
logger = logging.getLogger(__name__)
def fen_to_svg(fen_string, last_move=None):
    """
    Convert FEN string to SVG image data
    Returns base64 encoded SVG string
    """
    try:
        logger.info(f"Converting FEN to SVG: {fen_string[:50]}...")
        
        if not fen_string or fen_string.strip() == '':
            logger.error("Empty FEN string provided")
            return None
            
        board = chess.Board(fen_string)
        
        # Generate SVG
        if last_move:
            svg_bytes = chess.svg.board(board, lastmove=last_move, size=400)
        else:
            svg_bytes = chess.svg.board(board, size=400)
        
        # Convert to base64 for embedding in HTML
        encoded = base64.b64encode(svg_bytes.encode('utf-8')).decode('utf-8')
        logger.info("Successfully generated board SVG")
        return f"data:image/svg+xml;base64,{encoded}"
    
    except ValueError as e:
        logger.error(f"Invalid FEN string '{fen_string}': {e}")
        return None
    except Exception as e:
        logger.error(f"Error generating board SVG: {e}")
        return None

def get_last_move_from_moves(moves_string):
    """
    Extract the last move from a moves string (space-separated)
    Returns a chess.Move object or None
    """
    if not moves_string:
        return None
    
    try:
        moves = moves_string.strip().split()
        if moves:
            last_move_san = moves[-1]
            # Note: This is simplified - proper SAN to move conversion is complex
            # For now, we'll just return None and let the board render without highlighting
            return None
    except:
        pass
    return None

def fen_to_simple_pgn(fen, white_player, black_player, result, date):
    """Create a simple PGN from FEN and game info"""
    result_map = {'W': '1-0', 'L': '0-1', 'D': '1/2-1/2'}
    pgn_result = result_map.get(result, '*')
    
    pgn = f'''[Event "Chess.com Game"]
[Site "Chess.com"]
[Date "{date}"]
[White "{white_player}"]
[Black "{black_player}"]
[Result "{pgn_result}"]
[FEN "{fen}"]

*'''
    return pgn    