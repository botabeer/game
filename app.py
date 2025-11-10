from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, FlexSendMessage
)
import os
from datetime import datetime, timedelta
import sqlite3
from collections import defaultdict
import threading
import time
import re
import logging

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# استيراد الألعاب
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
    logger.info("تم استيراد جميع الألعاب بنجاح")
except Exception as e:
    logger.error(f"خطأ في استيراد الألعاب: {e}")

# تهيئة Flask
app = Flask(__name__)

# إعداد LINE Bot
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_CHANNEL_SECRET')

if LINE_CHANNEL_ACCESS_TOKEN == 'YOUR_CHANNEL_ACCESS_TOKEN':
    logger.warning("⚠️ لم يتم تعيين LINE_CHANNEL_ACCESS_TOKEN")
if LINE_CHANNEL_SECRET == 'YOUR_CHANNEL_SECRET':
    logger.warning("⚠️ لم يتم تعيين LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# إعداد مفاتيح Gemini للذكاء الاصطناعي
GEMINI_API_KEYS = [
    os.getenv('GEMINI_API_KEY_1', ''),
    os.getenv('GEMINI_API_KEY_2', ''),
    os.getenv('GEMINI_API_KEY_3', '')
]
GEMINI_API_KEYS = [key for key in GEMINI_API_KEYS if key]
current_gemini_key_index = 0
USE_AI = bool(GEMINI_API_KEYS)

logger.info(f"عدد مفاتيح Gemini المتاحة: {len(GEMINI_API_KEYS)}")
logger.info(f"استخدام AI: {USE_AI}")

def get_gemini_api_key():
    global current_gemini_key_index
    if GEMINI_API_KEYS:
        return GEMINI_API_KEYS[current_gemini_key_index]
    return None

def switch_gemini_key():
    global current_gemini_key_index
    if len(GEMINI_API_KEYS) > 1:
        current_gemini_key_index = (current_gemini_key_index + 1) % len(GEMINI_API_KEYS)
        logger.info(f"تم التبديل إلى مفتاح Gemini رقم: {current_gemini_key_index + 1}")
        return True
    return False

# بيانات اللعبة
active_games = {}
registered_players = set()
user_message_count = defaultdict(lambda: {'count': 0, 'reset_time': datetime.now()})
games_lock = threading.Lock()
players_lock = threading.Lock()

# دوال مساعدة
def normalize_text(text):
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r'^ال', '', text)
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    text = text.replace('ة', 'ه')
    text = text.replace('ى', 'ي')
    text = re.sub(r'[\u064B-\u065F]', '', text)
    return text

# قاعدة البيانات
DB_NAME = 'game_scores.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT,
                total_points INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                last_played TEXT,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                game_type TEXT,
                points INTEGER,
                won INTEGER,
                played_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_points ON users(total_points DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_game_history_user ON game_history(user_id, played_at)')
        conn.commit()
        conn.close()
        logger.info("تم إنشاء قاعدة البيانات بنجاح")
    except Exception as e:
        logger.error(f"خطأ في إنشاء قاعدة البيانات: {e}")

init_db()
# ------------------- Webhook -------------------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    logger.info(f"Incoming request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("⚠️ Invalid signature. تحقق من إعدادات LINE Channel Secret.")
        abort(400)
    except Exception as e:
        logger.error(f"خطأ أثناء معالجة الرسالة: {e}")
        abort(500)
    return 'OK'

# ------------------- إدارة الرسائل -------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text
    normalized_text = normalize_text(user_text)

    # تسجيل المستخدم إذا لم يكن مسجلاً
    with players_lock:
        if user_id not in registered_players:
            registered_players.add(user_id)
            try:
                conn = get_db_connection()
                conn.execute(
                    'INSERT OR IGNORE INTO users (user_id, display_name) VALUES (?, ?)',
                    (user_id, f'User_{user_id[-4:]}')
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"خطأ أثناء تسجيل المستخدم: {e}")

    # الحد من عدد الرسائل في الدقيقة
    user_data = user_message_count[user_id]
    now = datetime.now()
    if now >= user_data['reset_time']:
        user_data['count'] = 0
        user_data['reset_time'] = now + timedelta(minutes=1)

    if user_data['count'] >= 30:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ وصلت الحد المسموح من الرسائل، انتظر قليلاً.")
        )
        return
    user_data['count'] += 1

    # اختيار اللعبة النشطة إذا كانت موجودة
    game = active_games.get(user_id)
    if game:
        try:
            response = game.process(user_text)
            if response:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=response)
                )
        except Exception as e:
            logger.error(f"خطأ في اللعبة النشطة للمستخدم {user_id}: {e}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ حدث خطأ أثناء معالجة لعبتك.")
            )
    else:
        # إذا لم يكن هناك لعبة نشطة، نعرض قائمة الألعاب
        reply_text = "اختر لعبة للعب:\n1. IQ Game\n2. Word Color Game\n3. Chain Words\n4. Scramble Word\n5. Letters Words\n6. Fast Typing\n7. Human/Animal/Plant\n8. Guess Game\n9. Compatibility\n10. Math Game\n11. Memory Game\n12. Riddles\n13. Opposite Game\n14. Emoji Game\n15. Song Game\nأرسل الرقم لبدء اللعبة."
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )

# ------------------- دوال مساعدة للألعاب -------------------
def start_game(user_id, game_type):
    with games_lock:
        if game_type == 'IQ':
            active_games[user_id] = IQGame(line_bot_api, use_ai=USE_AI, get_api_key=get_gemini_api_key, switch_key=switch_gemini_key)
        # يمكن إضافة جميع الألعاب الأخرى بنفس الطريقة
        # active_games[user_id] = OtherGame(...)
        logger.info(f"تم بدء لعبة {game_type} للمستخدم {user_id}")

def end_game(user_id):
    with games_lock:
        if user_id in active_games:
            del active_games[user_id]
            logger.info(f"تم إنهاء اللعبة للمستخدم {user_id}")

# ------------------- تشغيل التطبيق -------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 بدء الخادم على المنفذ {port}")
    logger.info(f"📊 عدد اللاعبين المسجلين: {len(registered_players)}")
    logger.info(f"🎮 عدد الألعاب النشطة: {len(active_games)}")
    app.run(host='0.0.0.0', port=port, debug=False)
