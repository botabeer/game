"""
لعبة تكوين كلمات من حروف معينة
"""
from linebot.models import TextSendMessage
from .base_game import BaseGame
import random


class LettersWordsGame(BaseGame):
    """لعبة تكوين كلمات من مجموعة حروف"""

    def __init__(self, line_bot_api, use_ai=False, get_api_key=None, switch_key=None):
        super().__init__(line_bot_api, questions_count=10)

        # مجموعات الحروف مع جميع الكلمات الممكنة
        self.letter_sets = [
            {"letters": "ق ل م ع ر ب", "words": ["قلم", "عمل", "علم", "قلب", "رقم", "مقر"]},
            {"letters": "س ا ر ة ي", "words": ["سيارة", "سارية", "رئيس", "أسر", "سير"]},
            {"letters": "ك ت ا ب", "words": ["كتاب", "بت", "كتب", "تاب"]},
            {"letters": "م د ر س ة", "words": ["مدرسة", "درس", "سمر", "رمس", "سرد"]},
            {"letters": "ح د ي ق ة", "words": ["حديقة", "قيد", "قدح", "يحد", "حقي"]},
            {"letters": "ط ا ئ ر ة", "words": ["طائرة", "طار", "أطار", "رأى", "إطار"]},
        ]

        random.shuffle(self.letter_sets)
        self.found_words = set()
        self.required_words = 3
        self.game_active = False

    def start_game(self):
        """بدء اللعبة"""
        self.current_question = 0
        self.game_active = True
        return self.get_question()

    def get_question(self):
        """إرسال الحروف الحالية للّاعب"""
        letter_set = self.letter_sets[self.current_question % len(self.letter_sets)]
        self.current_answer = letter_set["words"]
        self.found_words.clear()

        message = f"🎯 لعبة تكوين كلمات ({self.current_question + 1}/{self.questions_count})\n\n"
        message += f"🔠 الحروف المتاحة:\n『 {letter_set['letters']} 』\n\n"
        message += f"كوّن {self.required_words} كلمات من هذه الحروف\n"
        message += "✏️ أرسل كل كلمة في رسالة مستقلة\n"
        message += "➡️ اكتب 'تم' للانتقال للسؤال التالي"

        return TextSendMessage(text=message)

    def check_answer(self, user_answer, user_id, display_name):
        """تحقق من الكلمة المدخلة"""
        if not self.game_active:
            return None

        answer = user_answer.strip()
        # الانتقال للسؤال التالي
        if answer in ['تم', 'التالي', 'next']:
            if len(self.found_words) >= self.required_words:
                return self.next_question_message()
            else:
                remaining = self.required_words - len(self.found_words)
                msg = f"يجب أن تجد {remaining} كلمة أخرى على الأقل!"
                return {'message': msg, 'response': TextSendMessage(text=msg), 'points': 0}

        normalized = self.normalize_text(answer)
        # التحقق من الكلمة الصحيحة ضمن الكلمات المسموح بها
        valid_words = [self.normalize_text(w) for w in self.current_answer]

        if normalized in self.found_words:
            msg = f"⚠️ الكلمة '{user_answer}' تم اكتشافها سابقًا!"
            return {'message': msg, 'response': TextSendMessage(text=msg), 'points': 0}

        if normalized in valid_words:
            self.found_words.add(normalized)
            points = self.add_score(user_id, display_name, 10)

            if len(self.found_words) >= self.required_words:
                msg = f"✅ أحسنت يا {display_name}! اكتشفت {self.required_words} كلمات صحيحة 🎉\n+{points} نقطة\n"
                return self.next_question_message(points=points, extra_msg=msg)
            else:
                remaining = self.required_words - len(self.found_words)
                msg = f"✅ كلمة صحيحة يا {display_name}!\n+{points} نقطة\n"
                msg += f"💡 تبقّى {remaining} كلمة\n"
                msg += "✏️ اكتب 'تم' للانتقال للسؤال التالي"
                return {'message': msg, 'response': TextSendMessage(text=msg), 'points': points}

        msg = f"❌ الكلمة '{user_answer}' غير صحيحة أو غير موجودة ضمن الكلمات الممكنة!"
        return {'message': msg, 'response': TextSendMessage(text=msg), 'points': 0}

    def next_question_message(self, points=0, extra_msg=""):
        """الانتقال للسؤال التالي"""
        self.current_question += 1

        if self.current_question >= self.questions_count:
            self.game_active = False
            msg = extra_msg + "\n🏁 انتهت اللعبة! شكراً لمشاركتك 🌟"
            return {'message': msg, 'response': TextSendMessage(text=msg), 'game_over': True, 'points': points}

        next_q = self.get_question()
        msg = extra_msg + "\n" + next_q.text
        return {'message': msg, 'response': TextSendMessage(text=msg), 'points': points}

    def normalize_text(self, text):
        """تطبيع النص"""
        return ''.join(text.split())
