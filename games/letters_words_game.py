from linebot.models import TextSendMessage
from .base_game import BaseGame
import random

class LettersWordsGame(BaseGame):
    """لعبة تكوين كلمات من مجموعة حروف"""

    def __init__(self, line_bot_api, use_ai=False, get_api_key=None, switch_key=None):
        super().__init__(line_bot_api, questions_count=10)

        self.letter_sets = [
            {"letters": "ق ل م ع ر ب"},
            {"letters": "س ا ر ة ي"},
            {"letters": "ك ت ا ب"},
            {"letters": "م د ر س ة"},
            {"letters": "ط ا ئ ر ة"},
            {"letters": "ح د ي ق ة"}
            # أضف المزيد عند الحاجة
        ]
        random.shuffle(self.letter_sets)
        self.found_words = set()
        self.required_words = 3

    def start_game(self):
        """بدء اللعبة"""
        self.current_question = 0
        self.found_words.clear()
        return self.get_question()

    def get_question(self):
        """الحصول على السؤال الحالي"""
        letter_set = self.letter_sets[self.current_question % len(self.letter_sets)]
        self.letters = set(letter_set['letters'].split())
        self.found_words.clear()

        message = f"تكوين كلمات ({self.current_question + 1}/{self.questions_count})\n"
        message += f"الحروف المتاحة:\n『 {' '.join(self.letters)} 』\n"
        message += f"كوّن {self.required_words} كلمات من هذه الحروف\n"
        message += "اكتب 'تم' للانتقال للسؤال التالي"

        return TextSendMessage(text=message)

    def check_answer(self, user_answer, user_id, display_name):
        """تحقق من صحة الكلمة المدخلة"""
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

        # فحص الكلمة: هل جميع الحروف ضمن الحروف المتاحة؟
        normalized = self.normalize_text(answer)
        if normalized in self.found_words:
            msg = f"⚠️ الكلمة '{user_answer}' تم اكتشافها من قبل!"
            return {'message': msg, 'response': TextSendMessage(text=msg), 'points': 0}
        
        # الشروط المعتبرة: تتكون فقط من الحروف المعطاة، 2 حرف على الأقل مثلاً
        if len(normalized) >= 2 and all(char in self.letters for char in normalized):
            self.found_words.add(normalized)
            points = self.add_score(user_id, display_name, 10)
            if len(self.found_words) >= self.required_words:
                msg = f"✅ كلمة صحيحة يا {display_name}!\n+{points} نقطة\n🎉 ممتاز! اكتشفت ثلاث كلمات صحيحة\n"
                return self.next_question_message(points=points, extra_msg=msg)
            else:
                msg = f"✅ كلمة صحيحة يا {display_name}!\n+{points} نقطة\n"
                msg += f"💡 هناك {self.required_words - len(self.found_words)} كلمة أخرى\nاكتب 'تم' للانتقال للسؤال التالي"
                return {'message': msg, 'response': TextSendMessage(text=msg), 'points': points}

        msg = f"❌ الكلمة '{user_answer}' غير صحيحة! استعمل فقط الحروف المتاحة."
        return {'message': msg, 'response': TextSendMessage(text=msg), 'points': 0}

    def next_question_message(self, points=0, extra_msg=""):
        self.current_question += 1
        if self.current_question >= self.questions_count:
            msg = extra_msg + "\nانتهت اللعبة! شكراً لمشاركتك."
            return {'message': msg, 'response': TextSendMessage(text=msg), 'game_over': True, 'points': points}
        else:
            q_text = self.get_question().text
            msg = extra_msg + "\n" + q_text
            return {'message': msg, 'response': TextSendMessage(text=msg), 'points': points}

    def normalize_text(self, text):
        """تطبيع النص، حذف الحركات والمسافات"""
        return ''.join(text.split())
