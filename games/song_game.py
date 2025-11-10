"""
لعبة تخمين الأغنية من كلماتها
"""
from linebot.models import TextSendMessage
from .base_game import BaseGame
import random


class SongGame(BaseGame):
    """لعبة تخمين الأغنية"""
    
    def __init__(self, line_bot_api):
        super().__init__(line_bot_api, questions_count=10)
        
        # قائمة أغاني مشهورة مع مقاطع منها
        self.songs = [
            {
                "lyrics": "كل سنة وأنت طيب يا حبيبي",
                "title": "كل سنة وأنت طيب",
                "artist": "محمد عبد الوهاب"
            },
            {
                "lyrics": "حبيبي يا نور العين يا ساكن خيالي",
                "title": "نور العين",
                "artist": "عمرو دياب"
            },
            {
                "lyrics": "آه يا زمان يا زمان",
                "title": "آه يا زمان",
                "artist": "أم كلثوم"
            },
            {
                "lyrics": "تعالى أحبك تعالى أنا بهواك",
                "title": "تعالى أحبك",
                "artist": "محمد منير"
            },
            {
                "lyrics": "سيبوني اتفرج عليها",
                "title": "سيبوني",
                "artist": "عمرو دياب"
            },
            {
                "lyrics": "على بالي حبيبي وانت عمري",
                "title": "على بالي",
                "artist": "عمرو دياب"
            },
            {
                "lyrics": "أنا قلبي إليك ميال",
                "title": "قلبي إليك ميال",
                "artist": "أم كلثوم"
            },
            {
                "lyrics": "يا مسافر وحدك",
                "title": "يا مسافر وحدك",
                "artist": "أم كلثوم"
            },
            {
                "lyrics": "حبيبتي من تكون",
                "title": "حبيبتي من تكون",
                "artist": "كاظم الساهر"
            },
            {
                "lyrics": "ثلاث دقات قلبي في حبك بدق",
                "title": "ثلاث دقات",
                "artist": "أبو"
            },
            {
                "lyrics": "معلش يا قلبي معلش",
                "title": "معلش",
                "artist": "شيرين"
            },
            {
                "lyrics": "كل ما أقول التوبة",
                "title": "التوبة",
                "artist": "محمد فؤاد"
            },
            {
                "lyrics": "يا طير يا طاير طير",
                "title": "يا طير",
                "artist": "فيروز"
            },
            {
                "lyrics": "بكرة بتنسى",
                "title": "بكرة",
                "artist": "وائل كفوري"
            },
            {
                "lyrics": "ليه يا قلبي ليه",
                "title": "ليه يا قلبي",
                "artist": "عمرو دياب"
            }
        ]
        
        random.shuffle(self.songs)
    
    def start_game(self):
        """بدء اللعبة"""
        self.current_question = 0
        return self.get_question()
    
    def get_question(self):
        """الحصول على السؤال الحالي"""
        song = self.songs[self.current_question % len(self.songs)]
        self.current_answer = song["title"]
        
        message = f"🎵 خمن الأغنية ({self.current_question + 1}/{self.questions_count})\n\n"
        message += f"🎤 من الكلمات:\n\n"
        message += f"« {song['lyrics']} »\n\n"
        message += "💡 اكتب اسم الأغنية أو:\n"
        message += "• لمح - للحصول على تلميح\n"
        message += "• جاوب - لعرض الإجابة"
        
        return TextSendMessage(text=message)
    
    def get_hint(self):
        """الحصول على تلميح"""
        song = self.songs[self.current_question % len(self.songs)]
        return f"💡 تلميح: المطرب/ة: {song['artist']}"
    
    def check_answer(self, user_answer, user_id, display_name):
        """فحص الإجابة"""
        if not self.game_active:
            return None
        
        # التحقق من أن المستخدم لم يجب بعد
        if user_id in self.answered_users:
            return None
        
        # أوامر خاصة
        if user_answer == 'لمح':
            hint = self.get_hint()
            return {
                'message': hint,
                'response': TextSendMessage(text=hint),
                'points': 0
            }
        
        if user_answer == 'جاوب':
            song = self.songs[self.current_question % len(self.songs)]
            reveal = f"✅ الإجابة الصحيحة:\n🎵 {song['title']}\n🎤 {song['artist']}"
            next_q = self.next_question()
            
            if isinstance(next_q, dict) and next_q.get('game_over'):
                return next_q
            
            message = f"{reveal}\n\n" + next_q.text if hasattr(next_q, 'text') else reveal
            return {
                'message': message,
                'response': TextSendMessage(text=message),
                'points': 0
            }
        
        # فحص الإجابة
        normalized_answer = self.normalize_text(user_answer)
        normalized_correct = self.normalize_text(self.current_answer)
        
        # قبول الإجابة إذا كانت تحتوي على جزء من العنوان
        if normalized_correct in normalized_answer or normalized_answer in normalized_correct:
            points = self.add_score(user_id, display_name, 10)
            
            song = self.songs[self.current_question % len(self.songs)]
            
            # الانتقال للسؤال التالي
            next_q = self.next_question()
            
            if isinstance(next_q, dict) and next_q.get('game_over'):
                next_q['points'] = points
                return next_q
            
            message = f"✅ ممتاز يا {display_name}!\n"
            message += f"🎵 {song['title']}\n"
            message += f"🎤 {song['artist']}\n"
            message += f"+{points} نقطة\n\n"
            
            if hasattr(next_q, 'text'):
                message += next_q.text
            
            return {
                'message': message,
                'response': TextSendMessage(text=message),
                'points': points
            }
        
        return None
