from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, FlexSendMessage
import os, sqlite3, threading, time, re, logging
from datetime import datetime, timedelta
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from games.iq_game import IQGame
    from games.word_color_game import WordColorGame
    from games.chain_words_game import ChainWordsGame
    from games.scramble_word_game import ScrambleWordGame
    from games.letters_words_game import LettersWordsGame
    from games.fast_typing_game import FastTypingGame
    from games.human_animal_plant_game import HumanAnimalPlantGame
    from games.guess_game import GuessGame
    from games.compatibility_game import CompatibilityGame
    from games.math_game import MathGame
    from games.memory_game import MemoryGame
    from games.riddle_game import RiddleGame
    from games.opposite_game import OppositeGame
    from games.emoji_game import EmojiGame
    from games.song_game import SongGame
except Exception as e:
    logger.error(f"خطأ استيراد: {e}")

app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_SECRET')
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

GEMINI_API_KEYS = [k for k in [os.getenv(f'GEMINI_API_KEY_{i}', '') for i in range(1,4)] if k]
current_gemini_key_index = 0
USE_AI = bool(GEMINI_API_KEYS)

def get_gemini_api_key():
    return GEMINI_API_KEYS[current_gemini_key_index] if GEMINI_API_KEYS else None

def switch_gemini_key():
    global current_gemini_key_index
    if len(GEMINI_API_KEYS) > 1:
        current_gemini_key_index = (current_gemini_key_index + 1) % len(GEMINI_API_KEYS)
        return True
    return False

active_games, registered_players = {}, set()
user_message_count = defaultdict(lambda: {'count': 0, 'reset_time': datetime.now()})
games_lock, players_lock = threading.Lock(), threading.Lock()

def normalize_text(text):
    if not text: return ""
    text = text.strip().lower()
    text = re.sub(r'^ال', '', text)
    for old, new in [('أ','ا'),('إ','ا'),('آ','ا'),('ة','ه'),('ى','ي')]:
        text = text.replace(old, new)
    return re.sub(r'[\u064B-\u065F]', '', text)

DB_NAME = 'game_scores.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, display_name TEXT, total_points INTEGER DEFAULT 0, games_played INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, last_played TEXT, registered_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS game_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, game_type TEXT, points INTEGER, won INTEGER, played_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id))''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_points ON users(total_points DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_game_history_user ON game_history(user_id, played_at)')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"خطأ DB: {e}")

init_db()

def update_user_points(user_id, display_name, points, won=False, game_type=""):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        if user:
            c.execute('UPDATE users SET total_points = ?, games_played = ?, wins = ?, last_played = ?, display_name = ? WHERE user_id = ?',
                (user['total_points'] + points, user['games_played'] + 1, user['wins'] + (1 if won else 0), datetime.now().isoformat(), display_name, user_id))
        else:
            c.execute('INSERT INTO users (user_id, display_name, total_points, games_played, wins, last_played) VALUES (?, ?, ?, ?, ?, ?)',
                (user_id, display_name, points, 1, 1 if won else 0, datetime.now().isoformat()))
        if game_type:
            c.execute('INSERT INTO game_history (user_id, game_type, points, won) VALUES (?, ?, ?, ?)', (user_id, game_type, points, 1 if won else 0))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"خطأ تحديث: {e}")
        return False

def get_user_stats(user_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    except: return None

def get_leaderboard(limit=10):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT display_name, total_points, games_played, wins FROM users ORDER BY total_points DESC LIMIT ?', (limit,))
        leaders = c.fetchall()
        conn.close()
        return leaders
    except: return []

def check_rate_limit(user_id):
    now = datetime.now()
    user_data = user_message_count[user_id]
    if now - user_data['reset_time'] > timedelta(minutes=1):
        user_data['count'], user_data['reset_time'] = 0, now
    if user_data['count'] >= 20: return False
    user_data['count'] += 1
    return True

def cleanup_old_games():
    while True:
        try:
            time.sleep(300)
            with games_lock:
                to_delete = [gid for gid, data in active_games.items() if datetime.now() - data.get('created_at', datetime.now()) > timedelta(minutes=10)]
                for gid in to_delete: del active_games[gid]
        except: pass

threading.Thread(target=cleanup_old_games, daemon=True).start()

def get_quick_reply():
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=l, text=t)) for l,t in [
        ("أسرع","أسرع"),("ذكاء","ذكاء"),("لون","كلمة ولون"),("أغنية","أغنية"),("سلسلة","سلسلة"),
        ("ترتيب","ترتيب الحروف"),("تكوين","تكوين كلمات"),("لعبة","لعبة"),("خمن","خمن"),
        ("ضد","ضد"),("ذاكرة","ذاكرة"),("لغز","لغز"),("رياضيات","رياضيات")]])

def get_user_profile_safe(user_id):
    try: return line_bot_api.get_profile(user_id).display_name
    except: return "مستخدم"

def start_game(game_id, game_class, game_type, user_id, event):
    try:
        with games_lock:
            game = game_class(line_bot_api, use_ai=USE_AI, get_api_key=get_gemini_api_key, switch_key=switch_gemini_key) if game_class in [IQGame, WordColorGame, LettersWordsGame, HumanAnimalPlantGame] else game_class(line_bot_api)
            with players_lock:
                participants = registered_players.copy()
                participants.add(user_id)
            active_games[game_id] = {'game': game, 'type': game_type, 'created_at': datetime.now(), 'participants': participants}
        line_bot_api.reply_message(event.reply_token, game.start_game())
        return True
    except Exception as e:
        logger.error(f"خطأ بدء: {e}")
        return False

@app.route("/")
def home():
    return f'<h1>LINE Bot</h1><p>Online ✓</p><p>Players: {len(registered_players)} | Games: {len(active_games)}</p>'

@app.route("/callback", methods=['POST'])
def callback():
    try:
        handler.handle(request.get_data(as_text=True), request.headers.get('X-Line-Signature', ''))
    except InvalidSignatureError: abort(400)
    except Exception as e: logger.error(f"Webhook: {e}")
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_id, text = event.source.user_id, event.message.text.strip()
        if not check_rate_limit(user_id):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ انتظر دقيقة", quick_reply=get_quick_reply()))
            return
        
        display_name = get_user_profile_safe(user_id)
        game_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
        
        if text in ['البداية','ابدأ','start']:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"مرحباً {display_name}\n\nاكتب 'انضم' للتسجيل", quick_reply=get_quick_reply()))
        elif text == 'مساعدة':
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الأوامر:\n• انضم\n• نقاطي\n• الصدارة\n• إيقاف", quick_reply=get_quick_reply()))
        elif text == 'نقاطي':
            stats = get_user_stats(user_id)
            msg = f"النقاط: {stats['total_points']}\nالألعاب: {stats['games_played']}" if stats else "لم تلعب بعد"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=get_quick_reply()))
        elif text == 'الصدارة':
            leaders = get_leaderboard()
            msg = "لوحة الصدارة\n\n" + "\n".join([f"{i}. {l['display_name']}: {l['total_points']}" for i,l in enumerate(leaders,1)]) if leaders else "لا بيانات"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=get_quick_reply()))
        elif text in ['إيقاف','ايقاف']:
            with games_lock:
                if game_id in active_games: del active_games[game_id]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم الإيقاف", quick_reply=get_quick_reply()))
        elif text == 'انضم':
            with players_lock: registered_players.add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"مرحباً {display_name}!", quick_reply=get_quick_reply()))
        elif text == 'انسحب':
            with players_lock: registered_players.discard(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم الانسحاب", quick_reply=get_quick_reply()))
        else:
            games_map = {
                'ذكاء':(IQGame,'ذكاء'), 'كلمة ولون':(WordColorGame,'لون'), 'لون':(WordColorGame,'لون'),
                'سلسلة':(ChainWordsGame,'سلسلة'), 'ترتيب الحروف':(ScrambleWordGame,'ترتيب'), 'ترتيب':(ScrambleWordGame,'ترتيب'),
                'تكوين كلمات':(LettersWordsGame,'تكوين'), 'تكوين':(LettersWordsGame,'تكوين'),
                'أسرع':(FastTypingGame,'أسرع'), 'لعبة':(HumanAnimalPlantGame,'لعبة'),
                'خمن':(GuessGame,'خمن'), 'توافق':(CompatibilityGame,'توافق'),
                'رياضيات':(MathGame,'رياضيات'), 'ذاكرة':(MemoryGame,'ذاكرة'),
                'لغز':(RiddleGame,'لغز'), 'ضد':(OppositeGame,'ضد'),
                'إيموجي':(EmojiGame,'إيموجي'), 'أغنية':(SongGame,'أغنية')
            }
            if text in games_map:
                if text == 'توافق':
                    with games_lock, players_lock:
                        game = CompatibilityGame(line_bot_api)
                        active_games[game_id] = {'game': game, 'type': 'توافق', 'created_at': datetime.now(), 'participants': registered_players.copy() | {user_id}}
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب اسمين", quick_reply=get_quick_reply()))
                else:
                    start_game(game_id, games_map[text][0], games_map[text][1], user_id, event)
            elif game_id in active_games:
                game_data = active_games[game_id]
                with players_lock: is_reg = user_id in registered_players
                if is_reg or user_id in game_data.get('participants', set()):
                    try:
                        result = game_data['game'].check_answer(text, user_id, display_name)
                        if result:
                            if result.get('points', 0) > 0:
                                update_user_points(user_id, display_name, result['points'], result.get('won', False), game_data['type'])
                            if result.get('game_over'):
                                with games_lock:
                                    if game_id in active_games: del active_games[game_id]
                            response = result.get('response', TextSendMessage(text=result.get('message', '')))
                            if isinstance(response, TextSendMessage): response.quick_reply = get_quick_reply()
                            line_bot_api.reply_message(event.reply_token, response)
                    except Exception as e:
                        logger.error(f"خطأ إجابة: {e}")
    except Exception as e:
        logger.error(f"خطأ معالجة: {e}")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True, debug=False)
