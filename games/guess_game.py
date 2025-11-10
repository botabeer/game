"""
لعبة تخمين الأرقام
"""
from linebot.models import TextSendMessage
from .base_game import BaseGame
import random


class GuessGame(BaseGame):
    """لعبة تخمين الرقم"""
    
    def __init__(self, line_bot_api):
        super().__init__(line_bot_api, questions_count=10)
        self.min_range = 1
        self.max_range = 50
        self.attempts = {}  # عدد المحاولات لكل لاعب
    
    def start_game(self):
        """بدء اللعبة"""
        self.current_question = 0
        return self.get_question()
    
    def get_question(self):
        """توليد رقم جديد"""
        # زيادة النطاق تدريجياً
        self.max_range = 50 + (self.current_question * 10)
        self.current_answer = random.randint(self.min_range, self.max_range)
        self.attempts = {}
        
        message = f"❓ خمن الرقم ({self.current_question + 1}/{self.questions_count})\n\n"
        message += f"🎯 خمن رقم بين {self.min_range} و {self.max_range}\n\n"
        message += "💡 سأخبرك إذا كان الرقم أكبر أو أصغر"
        
        return TextSendMessage(text=message)
    
    def check_answer(self, user_answer, user_id, display_name):
        """فحص التخمين"""
        if not self.game_active:
            return None
        
        # أوامر خاصة
        if user_answer == 'جاوب':
            reveal = self.reveal_answer()
            next_q = self.next_question()
            
            if isinstance(next_q, dict) and next_q.get('game_over'):
                return next_q
            
            message = f"{reveal}\n\n" + next_q.text if hasattr(next_q, 'text') else reveal
            return {
                'message': message,
                'response': TextSendMessage(text=message),
                'points': 0
            }
        
        # محاولة تحويل الإجابة لرقم
        try:
            guess = int(user_answer.strip())
            
            # التحقق من أن الرقم في النطاق
            if guess < self.min_range or guess > self.max_range:
                return {
                    'message': f"⚠️ الرقم يجب أن يكون بين {self.min_range} و {self.max_range}",
                    'response': TextSendMessage(text=f"⚠️ الرقم يجب أن يكون بين {self.min_range} و {self.max_range}"),
                    'points': 0
                }
            
            # زيادة عدد المحاولات
            if user_id not in self.attempts:
                self.attempts[user_id] = 0
            self.attempts[user_id] += 1
            
            correct_num = int(self.current_answer)
            
            if guess == correct_num:
                # إجابة صحيحة
                # منح نقاط حسب عدد المحاولات (كلما أقل محاولات كلما أكثر نقاط)
                base_points = 15 - min(self.attempts[user_id], 10)
                points = max(base_points, 5)  # على الأقل 5 نقاط
                
                self.add_score(user_id, display_name, points)
                
                # الانتقال للسؤال التالي
                next_q = self.next_question()
                
                if isinstance(next_q, dict) and next_q.get('game_over'):
                    next_q['points'] = points
                    return next_q
                
                message = f"🎉 ممتاز يا {display_name}!\n"
                message += f"✅ الرقم الصحيح: {correct_num}\n"
                message += f"🎯 عدد المحاولات: {self.attempts[user_id]}\n"
                message += f"+{points} نقطة\n\n"
                
                if hasattr(next_q, 'text'):
                    message += next_q.text
                
                return {
                    'message': message,
                    'response': TextSendMessage(text=message),
                    'points': points
                }
            
            elif guess < correct_num:
                # الرقم أصغر
                return {
                    'message': f"📈 الرقم أكبر من {guess}\nحاول مرة أخرى!",
                    'response': TextSendMessage(text=f"📈 الرقم أكبر من {guess}\nحاول مرة أخرى!"),
                    'points': 0
                }
            
            else:
                # الرقم أكبر
                return {
                    'message': f"📉 الرقم أصغر من {guess}\nحاول مرة أخرى!",
                    'response': TextSendMessage(text=f"📉 الرقم أصغر من {guess}\nحاول مرة أخرى!"),
                    'points': 0
                }
        
        except ValueError:
            return None
        
        return None
