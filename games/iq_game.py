"""
لعبة أسئلة الذكاء مع دعم Gemini AI
"""
from linebot.models import TextSendMessage
from .base_game import BaseGame
import random
import re


class IQGame(BaseGame):
    """لعبة أسئلة الذكاء"""
    
    def __init__(self, line_bot_api, use_ai=False, get_api_key=None, switch_key=None):
        super().__init__(line_bot_api, questions_count=10)
        self.use_ai = use_ai
        self.get_api_key = get_api_key
        self.switch_key = switch_key
        
        # أسئلة جاهزة
        self.questions = [
            {"q": "ما هو الشيء الذي يمشي بلا أرجل ويبكي بلا عيون؟", "a": "السحاب"},
            {"q": "ما هو الشيء الذي له رأس ولا يملك عيون؟", "a": "الدبوس"},
            {"q": "شيء موجود في السماء إذا أضفت له حرفاً أصبح في الأرض؟", "a": "نجم"},
            {"q": "ما هو الشيء الذي كلما زاد نقص؟", "a": "العمر"},
            {"q": "له عين ولا يرى؟", "a": "الإبرة"},
            {"q": "ما هو الشيء الذي يكتب ولا يقرأ؟", "a": "القلم"},
            {"q": "شيء إذا أكلته كله تستفيد وإذا أكلت نصفه تموت؟", "a": "السمسم"},
            {"q": "ما هو البيت الذي ليس له أبواب ولا نوافذ؟", "a": "بيت الشعر"},
            {"q": "شيء له أسنان ولا يعض؟", "a": "المشط"},
            {"q": "ما هو الشيء الذي يسمع بلا أذن ويتكلم بلا لسان؟", "a": "الهاتف"},
            {"q": "أنا ابن الماء فإن تركوني في الماء مت، فمن أنا؟", "a": "الثلج"},
            {"q": "شيء يوجد في وسط باريس؟", "a": "حرف الراء"},
            {"q": "ما هو الشيء الذي يقرصك ولا تراه؟", "a": "الجوع"},
            {"q": "له رقبة وليس له رأس؟", "a": "الزجاجة"},
            {"q": "ما هو الحيوان الذي يحك أذنه بأنفه؟", "a": "الفيل"},
            {"q": "شيء موجود في كل شيء؟", "a": "الاسم"},
            {"q": "كلما أخذت منه كبر؟", "a": "الحفرة"},
            {"q": "ما هو الطائر الذي يلد ولا يبيض؟", "a": "الخفاش"},
            {"q": "شيء يملك عينين ولا يرى؟", "a": "المقص"},
            {"q": "ما هو الشيء الذي تراه في الليل ثلاث مرات وفي النهار مرة واحدة؟", "a": "حرف اللام"}
        ]
        
        random.shuffle(self.questions)
    
    def generate_ai_question(self):
        """توليد سؤال باستخدام Gemini AI"""
        if not self.use_ai or not self.get_api_key:
            return None
        
        try:
            import google.generativeai as genai
            
            api_key = self.get_api_key()
            if not api_key:
                return None
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = """أنشئ سؤال ذكاء عربي واحد فقط مع الإجابة.
            
            الصيغة المطلوبة:
            السؤال: [السؤال هنا]
            الإجابة: [الإجابة هنا]
            
            يجب أن يكون السؤال:
            - مناسب لجميع الأعمار
            - بسيط وممتع
            - باللغة العربية الفصحى
            - إجابته كلمة واحدة أو كلمتين"""
            
            response = model.generate_content(prompt)
            text = response.text
            
            # استخراج السؤال والإجابة
            question_match = re.search(r'السؤال:\s*(.+?)(?=الإجابة:|$)', text, re.DOTALL)
            answer_match = re.search(r'الإجابة:\s*(.+?)(?=$)', text, re.DOTALL)
            
            if question_match and answer_match:
                question = question_match.group(1).strip()
                answer = answer_match.group(1).strip()
                return {"q": question, "a": answer}
            
            return None
            
        except Exception as e:
            print(f"خطأ في توليد السؤال بالـ AI: {e}")
            if self.switch_key and self.switch_key():
                return self.generate_ai_question()
            return None
    
    def start_game(self):
        """بدء اللعبة"""
        self.current_question = 0
        return self.get_question()
    
    def get_question(self):
        """الحصول على السؤال الحالي"""
        # محاولة توليد سؤال بالـ AI
        if self.use_ai and random.random() < 0.5:  # 50% فرصة لاستخدام AI
            ai_question = self.generate_ai_question()
            if ai_question:
                question_data = ai_question
            else:
                question_data = self.questions[self.current_question % len(self.questions)]
        else:
            question_data = self.questions[self.current_question % len(self.questions)]
        
        self.current_answer = question_data["a"]
        
        message = f"🧠 سؤال ذكاء ({self.current_question + 1}/{self.questions_count})\n\n"
        message += f"❓ {question_data['q']}\n\n"
        message += "💡 اكتب الإجابة أو:\n"
        message += "• لمح - للحصول على تلميح\n"
        message += "• جاوب - لعرض الإجابة"
        
        return TextSendMessage(text=message)
    
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
        
        # فحص الإجابة
        normalized_answer = self.normalize_text(user_answer)
        normalized_correct = self.normalize_text(self.current_answer)
        
        if normalized_answer == normalized_correct or normalized_answer in normalized_correct:
            points = self.add_score(user_id, display_name, 10)
            
            # الانتقال للسؤال التالي
            next_q = self.next_question()
            
            if isinstance(next_q, dict) and next_q.get('game_over'):
                next_q['points'] = points
                return next_q
            
            message = f"✅ إجابة صحيحة يا {display_name}!\n+{points} نقطة\n\n"
            if hasattr(next_q, 'text'):
                message += next_q.text
            
            return {
                'message': message,
                'response': TextSendMessage(text=message),
                'points': points
            }
        
        return None
