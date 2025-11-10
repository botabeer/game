"""
لعبة تكوين كلمات من حروف معينة
"""
from linebot.models import TextSendMessage
from .base_game import BaseGame
import random


class LettersWordsGame(BaseGame):
    """لعبة تكوين كلمات من حروف"""
    
    def __init__(self, line_bot_api, use_ai=False, get_api_key=None, switch_key=None):
        super().__init__(line_bot_api, questions_count=10)
        
        # مجموعات حروف مع كلمات ممكنة
        self.letter_sets = [
            {"letters": "س ا ر ة ي", "words": ["سيارة", "سارية"]},
            {"letters": "ك ت ا ب", "words": ["كتاب"]},
            {"letters": "م د ر س ة", "words": ["مدرسة"]},
            {"letters": "ق ل م", "words": ["قلم"]},
            {"letters": "ش ج ر ة", "words": ["شجرة"]},
            {"letters": "ط ا ئ ر ة", "words": ["طائرة"]},
            {"letters": "ح د ي ق ة", "words": ["حديقة"]},
            {"letters": "م ك ت ب ة", "words": ["مكتبة"]},
            {"letters": "ه ا ت ف", "words": ["هاتف"]},
            {"letters": "ح ا س و ب", "words": ["حاسوب"]},
            {"letters": "م ط ب خ", "words": ["مطبخ"]},
            {"letters": "غ ر ف ة", "words": ["غرفة"]},
            {"letters": "ن ا ف ذ ة", "words": ["نافذة"]},
            {"letters": "م س ت ش ف ى", "words": ["مستشفى"]},
            {"letters": "ج ا م ع ة", "words": ["جامعة"]}
        ]
        
        random.shuffle(self.letter_sets)
        self.found_words = set()
        self.required_words = 3  # عدد الكلمات المطلوبة
    
    def start_game(self):
        """بدء اللعبة"""
        self.current_question = 0
        return self.get_question()
    
    def get_question(self):
        """الحصول على السؤال الحالي"""
        letter_set = self.letter_sets[self.current_question % len(self.letter_sets)]
        self.current_answer = letter_set["words"]
        self.found_words.clear()
        
        message = f"تكوين كلمات ({self.current_question + 1}/{self.questions_count})\n\n"
        message += f"الحروف المتاحة:\n\n"
        message += f"『 {letter_set['letters']} 』\n\n"
        message += f"كوّن {self.required_words} كلمات من هذه الحروف\n"
        message += "• اكتب 'تم' للانتقال للسؤال التالي"
        
        return TextSendMessage(text=message)
    
    def check_answer(self, user_answer, user_id, display_name):
        """فحص الإجابة"""
        if not self.game_active:
            return None
        
        # الانتقال للسؤال التالي
        if user_answer.strip() in ['تم', 'التالي', 'next']:
            if len(self.found_words) >= self.required_words:
                next_q = self.next_question()
                
                if isinstance(next_q, dict) and next_q.get('game_over'):
                    return next_q
                
                message = f"ننتقل للسؤال التالي\n\n"
                if hasattr(next_q, 'text'):
                    message += next_q.text
                
                return {
                    'message': message,
                    'response': TextSendMessage(text=message),
                    'points': 0
                }
            else:
                remaining = self.required_words - len(self.found_words)
                return {
                    'message': f"يجب أن تجد {remaining} كلمة أخرى على الأقل!",
                    'response': TextSendMessage(text=f"يجب أن تجد {remaining} كلمة أخرى على الأقل!"),
                    'points': 0
                }
        
        # فحص الكلمة
        normalized_answer = self.normalize_text(user_answer)
        
        # التحقق من أن الكلمة صحيحة
        for word in self.current_answer:
            if self.normalize_text(word) == normalized_answer:
                # التحقق من أنها لم تُكتشف من قبل
                if normalized_answer in self.found_words:
                    return {
                        'message': f"⚠️ الكلمة '{user_answer}' تم اكتشافها من قبل!",
                        'response': TextSendMessage(text=f"⚠️ الكلمة '{user_answer}' تم اكتشافها من قبل!"),
                        'points': 0
                    }
                
                # إضافة الكلمة للمكتشفة
                self.found_words.add(normalized_answer)
                points = self.add_score(user_id, display_name, 10)
                
                # التحقق من اكتشاف جميع الكلمات
                all_found = all(self.normalize_text(w) in self.found_words for w in self.current_answer)
                
                message = f"✅ كلمة صحيحة يا {display_name}!\n+{points} نقطة\n\n"
                
                if all_found:
                    message += "🎉 ممتاز! اكتشفت جميع الكلمات\n\n"
                    next_q = self.next_question()
                    
                    if isinstance(next_q, dict) and next_q.get('game_over'):
                        next_q['points'] = points
                        return next_q
                    
                    if hasattr(next_q, 'text'):
                        message += next_q.text
                else:
                    message += f"💡 هناك {len(self.current_answer) - len(self.found_words)} كلمة أخرى\n"
                    message += "اكتب 'تم' للانتقال للسؤال التالي"
                
                return {
                    'message': message,
                    'response': TextSendMessage(text=message),
                    'points': points
                }
        
        return None
