import os
import logging
import sys
from dotenv import load_dotenv
from user_database import UserDatabase

# التحقق من إصدار Python
if sys.version_info < (3, 8):
    print("❌ يتطلب Python 3.8 أو أحدث")
    print(f"الإصدار الحالي: {sys.version}")
    sys.exit(1)

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError as e:
    print("❌ خطأ في استيراد مكتبة telegram:")
    print(f"   {e}")
    print("💡 جرب تشغيل: python fix_telegram_bot.py")
    sys.exit(1)

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError as e:
    print("❌ خطأ في استيراد مكتبات Google:")
    print(f"   {e}")
    print("💡 جرب تشغيل: pip install -r requirements.txt")
    sys.exit(1)

# تحميل المتغيرات البيئية
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغير عام لمثيل البوت
bot_instance = None

class TelegramAccountBot:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

        # إذا لم يتم العثور على ملف credentials، استخدم متغير البيئة مباشرة
        if not os.path.exists(self.credentials_file):
            self.credentials_file = None
        self.admin_username = os.getenv('ADMIN_USERNAME', 'jlsh1sa')
        self.admin_phone = os.getenv('ADMIN_PHONE', '0554611589')
        # قائمة معرفات الأدمن
        self.admin_ids = [
            6461427638,  # jlsh1sa
            1393989189   # Abodi - أدمن إضافي
        ]

        # إعداد قاعدة بيانات المستخدمين
        self.user_db = UserDatabase()

        # إعداد Google Sheets
        self.setup_google_sheets()

    def is_admin(self, username, user_id=None):
        """التحقق من صلاحيات الأدمن"""
        # التحقق من اسم المستخدم
        if username == self.admin_username:
            return True

        # التحقق من معرف المستخدم
        if user_id and user_id in self.admin_ids:
            return True

        return False

    def check_user_credits(self, user_id, required_credits=1):
        """التحقق من كريدت المستخدم"""
        return self.user_db.get_credits(user_id) >= required_credits

    def deduct_user_credits(self, user_id, amount=1):
        """خصم كريدت من المستخدم"""
        return self.user_db.deduct_credits(user_id, amount)

    def setup_google_sheets(self):
        """إعداد الاتصال مع Google Sheets"""
        try:
            # نطاقات الصلاحيات المطلوبة
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            # التحقق من وجود credentials في متغير البيئة أولاً
            # جرب جميع الأسماء المحتملة
            google_credentials = (
                os.getenv('GOOGLE_CREDENTIALS') or
                os.getenv('CREDENTIALS') or
                os.getenv('GOOGLE_SERVICE_ACCOUNT') or
                os.getenv('SERVICE_ACCOUNT_KEY')
            )

            logger.info(f"🔍 البحث عن credentials...")
            logger.info(f"📁 مسار الملف المحلي: {self.credentials_file}")
            logger.info(f"🌐 GOOGLE_CREDENTIALS موجود: {bool(os.getenv('GOOGLE_CREDENTIALS'))}")
            logger.info(f"🌐 CREDENTIALS موجود: {bool(os.getenv('CREDENTIALS'))}")
            logger.info(f"🌐 GOOGLE_SERVICE_ACCOUNT موجود: {bool(os.getenv('GOOGLE_SERVICE_ACCOUNT'))}")
            logger.info(f"🌐 SERVICE_ACCOUNT_KEY موجود: {bool(os.getenv('SERVICE_ACCOUNT_KEY'))}")
            logger.info(f"📄 ملف credentials.json موجود: {os.path.exists(self.credentials_file) if self.credentials_file else False}")

            # طباعة جميع متغيرات البيئة التي تحتوي على "CRED" أو "GOOGLE"
            env_vars = {k: v[:50] + "..." if len(v) > 50 else v for k, v in os.environ.items()
                       if 'CRED' in k.upper() or 'GOOGLE' in k.upper()}
            logger.info(f"🔍 متغيرات البيئة ذات الصلة: {env_vars}")

            # طباعة أول 100 حرف من credentials للتأكد
            if google_credentials:
                logger.info(f"📝 أول 100 حرف من credentials: {google_credentials[:100]}...")
            else:
                logger.error("❌ لم يتم العثور على أي متغير credentials")

            if google_credentials:
                try:
                    # استخدام credentials من متغير البيئة
                    import json
                    logger.info("🔄 محاولة تحليل JSON...")

                    # تنظيف المحتوى من أي مسافات أو أحرف غير مرغوبة
                    google_credentials = google_credentials.strip()

                    # إذا كان المحتوى مُرمز بـ base64، فك الترميز
                    if not google_credentials.startswith('{'):
                        try:
                            import base64
                            logger.info("🔄 محاولة فك ترميز base64...")
                            google_credentials = base64.b64decode(google_credentials).decode('utf-8')
                            logger.info("✅ تم فك ترميز base64 بنجاح")
                        except Exception as base64_error:
                            logger.error(f"❌ فشل فك ترميز base64: {base64_error}")

                    creds_dict = json.loads(google_credentials)
                    logger.info("✅ تم تحليل JSON بنجاح")

                    # التحقق من وجود الحقول المطلوبة
                    required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
                    missing_fields = [field for field in required_fields if field not in creds_dict]
                    if missing_fields:
                        logger.error(f"❌ حقول مفقودة في credentials: {missing_fields}")
                        raise ValueError(f"حقول مفقودة: {missing_fields}")

                    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                    logger.info("✅ تم تحميل credentials من متغير البيئة بنجاح")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ خطأ في تحليل JSON: {e}")
                    logger.error(f"❌ المحتوى الذي فشل في التحليل: {google_credentials[:200]}...")
                    raise
                except Exception as e:
                    logger.error(f"❌ خطأ في تحليل credentials من متغير البيئة: {e}")
                    raise
            elif self.credentials_file and os.path.exists(self.credentials_file):
                # استخدام ملف credentials.json المحلي
                logger.info("🔄 محاولة تحميل من الملف المحلي...")
                try:
                    credentials = Credentials.from_service_account_file(
                        self.credentials_file,
                        scopes=scopes
                    )
                    logger.info("✅ تم تحميل credentials من الملف المحلي بنجاح")
                except Exception as e:
                    logger.error(f"❌ خطأ في تحميل الملف المحلي: {e}")
                    raise
            else:
                logger.error("❌ لم يتم العثور على credentials في أي مكان")
                logger.error(f"❌ متغيرات البيئة المتاحة: {list(os.environ.keys())}")
                raise FileNotFoundError("لم يتم العثور على credentials في متغير البيئة أو الملف المحلي")

            # إنشاء عميل gspread
            logger.info("🔄 محاولة إنشاء عميل gspread...")
            self.gc = gspread.authorize(credentials)
            logger.info("✅ تم إنشاء عميل gspread بنجاح")

            # فتح الشيت
            logger.info(f"🔄 محاولة فتح الشيت بالمعرف: {self.sheet_id}")
            self.sheet = self.gc.open_by_key(self.sheet_id).sheet1

            logger.info("✅ تم الاتصال بـ Google Sheets بنجاح")

        except Exception as e:
            logger.error(f"خطأ في الاتصال بـ Google Sheets: {e}")
            self.gc = None
            self.sheet = None
    
    def find_available_account(self):
        """البحث عن أول حساب فارغ في الشيت"""
        try:
            if not self.sheet:
                return None

            # قراءة الأعمدة مباشرة لتجنب مشكلة العناوين المكررة
            email_col = self.sheet.col_values(1)  # العمود A
            password_col = self.sheet.col_values(2)  # العمود B
            status_col = self.sheet.col_values(3)  # العمود C

            # التأكد من أن القوائم لها نفس الطول
            max_len = max(len(email_col), len(password_col), len(status_col))
            email_col.extend([''] * (max_len - len(email_col)))
            password_col.extend([''] * (max_len - len(password_col)))
            status_col.extend([''] * (max_len - len(status_col)))

            # البحث عن أول حساب متاح (بدون حالة في العمود الثالث)
            for i in range(1, len(email_col)):  # البداية من الصف 2 (index 1)
                email = email_col[i].strip() if email_col[i] else ''
                password = password_col[i].strip() if password_col[i] else ''
                status = status_col[i].strip() if status_col[i] else ''

                if email and password and not status:
                    return {
                        'row': i + 1,  # رقم الصف الفعلي في الشيت
                        'email': email,
                        'password': password
                    }

            return None

        except Exception as e:
            logger.error(f"خطأ في البحث عن الحسابات: {e}")
            return None

    def find_multiple_accounts(self, count):
        """البحث عن عدة حسابات متاحة من الشيت"""
        try:
            if not self.sheet:
                return []

            # قراءة الأعمدة مباشرة لتجنب مشكلة العناوين المكررة
            email_col = self.sheet.col_values(1)  # العمود A
            password_col = self.sheet.col_values(2)  # العمود B
            status_col = self.sheet.col_values(3)  # العمود C

            # التأكد من أن القوائم لها نفس الطول
            max_len = max(len(email_col), len(password_col), len(status_col))
            email_col.extend([''] * (max_len - len(email_col)))
            password_col.extend([''] * (max_len - len(password_col)))
            status_col.extend([''] * (max_len - len(status_col)))

            available_accounts = []

            # البحث عن الحسابات المتاحة
            for i in range(1, len(email_col)):  # البداية من الصف 2 (index 1)
                if len(available_accounts) >= count:
                    break

                email = email_col[i].strip() if email_col[i] else ''
                password = password_col[i].strip() if password_col[i] else ''
                status = status_col[i].strip() if status_col[i] else ''

                if email and password and not status:
                    available_accounts.append({
                        'row': i + 1,  # رقم الصف الفعلي في الشيت
                        'email': email,
                        'password': password
                    })

            return available_accounts

        except Exception as e:
            logger.error(f"خطأ في البحث عن الحسابات المتعددة: {e}")
            return []
    
    def mark_account_as_used(self, row_number, user_id, username=None, first_name=None):
        """تحديث حالة الحساب إلى مُستخدم"""
        try:
            if not self.sheet:
                return False

            # تحديث عمود الحالة (العمود الثالث)
            self.sheet.update_cell(row_number, 3, "مُستخدم")  # عمود status

            # إضافة معرف المستخدم في عمود رابع (إذا كان موجود)
            user_info = str(user_id)
            if username:
                user_info += f" (@{username})"
            if first_name:
                user_info += f" - {first_name}"

            try:
                # محاولة إضافة معرف المستخدم في عمود رابع
                self.sheet.update_cell(row_number, 4, user_info)  # عمود User ID
            except:
                # إذا لم يكن هناك عمود رابع، لا بأس
                pass

            logger.info(f"تم تحديث الحساب في الصف {row_number} كمُستخدم للمستخدم {user_info}")
            return True

        except Exception as e:
            logger.error(f"خطأ في تحديث الحساب: {e}")
            return False

    def mark_multiple_accounts_as_used(self, accounts, user_id, username=None, first_name=None):
        """تحديث عدة حسابات كمُستخدمة"""
        try:
            if not self.sheet or not accounts:
                return False

            # إعداد معلومات المستخدم
            user_info = str(user_id)
            if username:
                user_info += f" (@{username})"
            if first_name:
                user_info += f" - {first_name}"

            # تحديث كل حساب
            for account in accounts:
                row_number = account['row']

                # تحديث عمود الحالة (العمود الثالث)
                self.sheet.update_cell(row_number, 3, "مُستخدم")

                try:
                    # محاولة إضافة معرف المستخدم في عمود رابع
                    self.sheet.update_cell(row_number, 4, user_info)
                except:
                    # إذا لم يكن هناك عمود رابع، لا بأس
                    pass

            logger.info(f"تم تحديث {len(accounts)} حساب كمُستخدم للمستخدم {user_info}")
            return True

        except Exception as e:
            logger.error(f"خطأ في تحديث الحسابات المتعددة: {e}")
            return False

    def count_available_accounts(self):
        """عد الحسابات المتاحة"""
        try:
            if not self.sheet:
                return 0

            all_records = self.sheet.get_all_records()
            count = 0

            for record in all_records:
                # محاولة قراءة البيانات بأسماء مختلفة للعناوين
                status = record.get('Status', record.get('status', '')).strip()
                email = record.get('Gmail', record.get('email', '')).strip()
                password = record.get('Password', record.get('password', '')).strip()

                if not status and email and password:
                    count += 1

            return count

        except Exception as e:
            logger.error(f"خطأ في عد الحسابات: {e}")
            return 0

    def get_stats(self):
        """جلب إحصائيات الحسابات"""
        try:
            if not self.sheet:
                return {
                    'available_accounts': 0,
                    'available_emails': 0,
                    'used_accounts': 0,
                    'used_emails': 0,
                    'total_accounts': 0,
                    'total_emails': 0
                }

            # إحصائيات حسابات يوتيوب (الأعمدة A, B, C)
            youtube_email_col = self.sheet.col_values(1)  # العمود A
            youtube_password_col = self.sheet.col_values(2)  # العمود B
            youtube_status_col = self.sheet.col_values(3)  # العمود C

            # إحصائيات حسابات شات جي بي تي (الأعمدة F, G, H)
            chatgpt_email_col = self.sheet.col_values(6)  # العمود F
            chatgpt_password_col = self.sheet.col_values(7)  # العمود G
            chatgpt_status_col = self.sheet.col_values(8)  # العمود H

            # حساب إحصائيات يوتيوب
            available_youtube = 0
            used_youtube = 0

            max_len_youtube = max(len(youtube_email_col), len(youtube_password_col), len(youtube_status_col))
            youtube_email_col.extend([''] * (max_len_youtube - len(youtube_email_col)))
            youtube_password_col.extend([''] * (max_len_youtube - len(youtube_password_col)))
            youtube_status_col.extend([''] * (max_len_youtube - len(youtube_status_col)))

            for i in range(1, len(youtube_email_col)):  # البداية من الصف 2
                email = youtube_email_col[i].strip() if youtube_email_col[i] else ''
                password = youtube_password_col[i].strip() if youtube_password_col[i] else ''
                status = youtube_status_col[i].strip() if youtube_status_col[i] else ''

                if email and password:
                    if status:
                        used_youtube += 1
                    else:
                        available_youtube += 1

            # حساب إحصائيات شات جي بي تي
            available_chatgpt = 0
            used_chatgpt = 0

            max_len_chatgpt = max(len(chatgpt_email_col), len(chatgpt_password_col), len(chatgpt_status_col))
            chatgpt_email_col.extend([''] * (max_len_chatgpt - len(chatgpt_email_col)))
            chatgpt_password_col.extend([''] * (max_len_chatgpt - len(chatgpt_password_col)))
            chatgpt_status_col.extend([''] * (max_len_chatgpt - len(chatgpt_status_col)))

            for i in range(1, len(chatgpt_email_col)):  # البداية من الصف 2
                email = chatgpt_email_col[i].strip() if chatgpt_email_col[i] else ''
                password = chatgpt_password_col[i].strip() if chatgpt_password_col[i] else ''
                status = chatgpt_status_col[i].strip() if chatgpt_status_col[i] else ''

                if email and password:
                    if status:
                        used_chatgpt += 1
                    else:
                        available_chatgpt += 1

            return {
                'available_accounts': available_youtube,
                'available_emails': available_chatgpt,
                'used_accounts': used_youtube,
                'used_emails': used_chatgpt,
                'total_accounts': available_youtube + used_youtube,
                'total_emails': available_chatgpt + used_chatgpt,
                # للتوافق مع الكود القديم
                'available': available_youtube + available_chatgpt,
                'used': used_youtube + used_chatgpt,
                'total': available_youtube + used_youtube + available_chatgpt + used_chatgpt
            }

        except Exception as e:
            logger.error(f"خطأ في جلب الإحصائيات: {e}")
            return {
                'available_accounts': 0,
                'available_emails': 0,
                'used_accounts': 0,
                'used_emails': 0,
                'total_accounts': 0,
                'total_emails': 0,
                'available': 0,
                'used': 0,
                'total': 0
            }

    def get_current_time(self):
        """جلب الوقت الحالي"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية"""
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    user_name = update.effective_user.first_name or "صديقي"

    # تحديث معلومات المستخدم في قاعدة البيانات (بدون توكنات ترحيب)
    is_new_user = bot_instance.user_db.update_user_info(user_id, username, user_name, give_welcome_credits=False)

    # الحصول على كريدت المستخدم
    user_credits = bot_instance.user_db.get_credits(user_id)

    # رسالة مختلفة للمستخدمين الجدد
    if is_new_user:
        welcome_message = f"""
🎉 **مرحباً {user_name}! أهلاً بك في بوت الحسابات**

💰 **رصيدك الحالي:** {user_credits} كريدت

🎯 **ما نقدمه لك:**
• حسابات يوتيوب جاهزة للاستخدام
• حسابات شات جي بي تي محققة
• جميع الحسابات مضمونة وآمنة

📋 **الأوامر المتاحة:**
📺 `/buy` - شراء حساب يوتيوب (1 كريدت)
🤖 `/email` - شراء حساب شات جي بي تي (1 كريدت)
💰 `/credits` - عرض رصيدك الحالي
📊 `/stats` - عرض الإحصائيات
❓ `/help` - عرض المساعدة التفصيلية

💳 **لشراء كريدت، تواصل مع الإدارة:**
📞 **واتساب:** {bot_instance.admin_phone}
💬 **تلقرام:** @{bot_instance.admin_username}
        """
    else:
        welcome_message = f"""
🎉 **مرحباً {user_name}! أهلاً بك مرة أخرى**

💰 **رصيدك الحالي:** {user_credits} كريدت

🎯 **ما يمكنني فعله لك:**
• توفير حسابات يوتيوب جاهزة للاستخدام (1 كريدت)
• توفير حسابات شات جي بي تي (1 كريدت)
• تتبع الحسابات المُستخدمة تلقائياً

📋 **الأوامر المتاحة:**
📺 `/buy` - شراء حساب يوتيوب (1 كريدت)
🤖 `/email` - شراء حساب شات جي بي تي (1 كريدت)
💰 `/credits` - عرض رصيدك الحالي
📊 `/stats` - عرض الإحصائيات
❓ `/help` - عرض المساعدة التفصيلية

💡 **للحصول على المزيد من الكريدت:**
📱 **تواصل مع الأدمن:** @{bot_instance.admin_username}
📞 **أو عبر الواتساب:** {bot_instance.admin_phone}

🚀 **ابدأ الآن بكتابة** `/buy` **للحصول على حسابك الأول!**
        """

    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    help_text = """
🤖 **مرحباً بك في بوت الحسابات!**

📋 **قائمة الأوامر:**

**🎯 الحسابات العادية:**
🛒 `/buy` - شراء حساب Gmail واحد
🛒 `/buy5` - شراء 5 حسابات دفعة واحدة
🛒 `/buy10` - شراء 10 حسابات دفعة واحدة

**📧 الإيميلات الجديدة:**
📧 `/email` - شراء إيميل واحد
� `/email5` - شراء 5 إيميلات دفعة واحدة
📧 `/email10` - شراء 10 إيميلات دفعة واحدة

📊 `/stats` - عرض إحصائيات الحسابات
❓ `/help` - عرض هذه المساعدة

💡 **كيفية الاستخدام:**
1. اكتب `/buy` للحصول على حساب عادي واحد
2. اكتب `/email` للحصول على إيميل جديد واحد
3. أضف رقم للحصول على عدة حسابات (مثل `/buy7` أو `/email3`)
4. ستحصل على Email + Password لكل حساب/إيميل
5. الحسابات ستصبح مُستخدمة تلقائياً

🔄 **الفرق بين الأوامر:**
• `/buy` - للحسابات العادية (من القائمة الأولى)
• `/email` - للإيميلات الجديدة (من القائمة الثانية)

📝 **أمثلة:**
• `/buy` - حساب عادي واحد
• `/buy3` - 3 حسابات عادية
• `/buy50` - 50 حساب عادي
• `/email` - إيميل جديد واحد
• `/email5` - 5 إيميلات جديدة
• `/email50` - 50 إيميل جديد
• الحد الأقصى: 100 حساب/إيميل في المرة الواحدة

⚠️ **ملاحظات مهمة:**
• احفظ بيانات الحسابات في مكان آمن
• لا تشارك البيانات مع أحد
• كل حساب/إيميل يُعطى مرة واحدة فقط
• الشراء المتعدد يوفر وقتك!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def buy_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر شراء حساب يوتيوب"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "غير محدد"
    first_name = update.effective_user.first_name or "غير محدد"

    # استخراج العدد من الأمر (مثل /buy5 أو /buy10)
    command_text = update.message.text.strip()
    count = 1  # افتراضي: حساب واحد

    # التحقق من وجود رقم في الأمر
    if command_text.startswith('/buy') and len(command_text) > 4:
        try:
            count = int(command_text[4:])  # استخراج الرقم بعد /buy
            if count <= 0 or count > 100:  # حد أقصى 100 حساب
                await update.message.reply_text("❌ العدد يجب أن يكون بين 1 و 100")
                return
        except ValueError:
            await update.message.reply_text("❌ صيغة الأمر غير صحيحة. استخدم /buy أو /buy50 مثلاً")
            return

    # التحقق من الكريدت
    if not bot_instance.check_user_credits(user_id, count):
        user_credits = bot_instance.user_db.get_credits(user_id)
        await update.message.reply_text(
            f"❌ **رصيدك غير كافي!**\n\n"
            f"💰 رصيدك الحالي: {user_credits} كريدت\n"
            f"💳 المطلوب: {count} كريدت\n\n"
            f"📞 **للحصول على كريدت:**\n"
            f"💬 تلقرام: @{bot_instance.admin_username}\n"
            f"📱 واتساب: {bot_instance.admin_phone}",
            parse_mode='Markdown'
        )
        return

    # إرسال رسالة انتظار
    if count == 1:
        waiting_message = await update.message.reply_text("🔍 جاري البحث عن حساب يوتيوب متاح...")
    else:
        waiting_message = await update.message.reply_text(f"🔍 جاري البحث عن {count} حساب يوتيوب متاح...")

    try:
        if count == 1:
            # شراء حساب واحد (الطريقة القديمة)
            account = bot_instance.find_available_account()

            if not account:
                available_count = bot_instance.count_available_accounts()
                await waiting_message.edit_text(
                    f"❌ عذراً، لا توجد حسابات متاحة حالياً.\n"
                    f"📊 عدد الحسابات المتاحة: {available_count}\n"
                    f"⏰ يرجى المحاولة لاحقاً أو التواصل مع الإدارة."
                )
                return

            success = bot_instance.mark_account_as_used(account['row'], user_id, username, first_name)

            if success:
                # خصم الكريدت
                bot_instance.deduct_user_credits(user_id, 1)
                remaining_credits = bot_instance.user_db.get_credits(user_id)

                account_message = f"""
✅ تم العثور على حساب يوتيوب لك!

📺 **حساب يوتيوب:** `{account['email']}`
🔐 **كلمة المرور:** `{account['password']}`

💰 **تم خصم 1 كريدت - رصيدك الحالي: {remaining_credits} كريدت**

⚠️ **ملاحظة مهمة:**
• هذا الحساب أصبح مُستخدم الآن ولن يُعطى لأحد آخر
• احفظ البيانات في مكان آمن
• لا تشارك هذه البيانات مع أحد

👤 **المستخدم:** {first_name} (@{username})
🆔 **معرف المستخدم:** `{user_id}`
🕐 **وقت الشراء:** {bot_instance.get_current_time()}
                """
                await waiting_message.edit_text(account_message, parse_mode='Markdown')
                logger.info(f"تم إعطاء حساب للمستخدم {user_id} (@{username}) - {first_name} - خصم 1 كريدت")
            else:
                await waiting_message.edit_text("❌ حدث خطأ في تحديث الحساب. يرجى المحاولة مرة أخرى.")

        else:
            # شراء عدة حسابات
            accounts = bot_instance.find_multiple_accounts(count)

            if not accounts:
                available_count = bot_instance.count_available_accounts()
                await waiting_message.edit_text(
                    f"❌ عذراً، لا توجد حسابات متاحة حالياً.\n"
                    f"📊 عدد الحسابات المتاحة: {available_count}\n"
                    f"⏰ يرجى المحاولة لاحقاً أو التواصل مع الإدارة."
                )
                return

            if len(accounts) < count:
                # إعطاء الحسابات المتاحة بدلاً من رفض الطلب
                await waiting_message.edit_text(
                    f"⚠️ تم العثور على {len(accounts)} حساب فقط من أصل {count} مطلوب.\n"
                    f"✅ سيتم إعطاؤك جميع الحسابات المتاحة ({len(accounts)} حساب)..."
                )
                # المتابعة مع الحسابات المتاحة

            success = bot_instance.mark_multiple_accounts_as_used(accounts, user_id, username, first_name)

            if success:
                # خصم الكريدت
                bot_instance.deduct_user_credits(user_id, len(accounts))
                remaining_credits = bot_instance.user_db.get_credits(user_id)

                # إنشاء رسالة الحسابات
                accounts_text = ""
                for i, account in enumerate(accounts, 1):
                    accounts_text += f"\n**حساب {i}:**\n📧 `{account['email']}`\n🔐 `{account['password']}`\n"

                accounts_message = f"""
✅ تم العثور على {len(accounts)} حساب يوتيوب لك!

{accounts_text}
💰 **تم خصم {len(accounts)} كريدت - رصيدك الحالي: {remaining_credits} كريدت**

⚠️ **ملاحظة مهمة:**
• هذه الحسابات أصبحت مُستخدمة الآن ولن تُعطى لأحد آخر
• احفظ البيانات في مكان آمن
• لا تشارك هذه البيانات مع أحد

👤 **المستخدم:** {first_name} (@{username})
🆔 **معرف المستخدم:** `{user_id}`
🕐 **وقت الشراء:** {bot_instance.get_current_time()}
                """
                await waiting_message.edit_text(accounts_message, parse_mode='Markdown')
                logger.info(f"تم إعطاء {len(accounts)} حساب للمستخدم {user_id} (@{username}) - {first_name} - خصم {len(accounts)} كريدت")
            else:
                await waiting_message.edit_text("❌ حدث خطأ في تحديث الحسابات. يرجى المحاولة مرة أخرى.")

    except Exception as e:
        logger.error(f"خطأ في أمر الشراء: {e}")
        await waiting_message.edit_text("❌ حدث خطأ غير متوقع. يرجى المحاولة لاحقاً.")

async def buy_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر شراء حساب شات جي بي تي من الأعمدة F, G, H"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "غير محدد"
    first_name = update.effective_user.first_name or "غير محدد"

    # استخراج العدد من الأمر (مثل /email5 أو /email10)
    command_text = update.message.text.strip()
    count = 1  # افتراضي: إيميل واحد

    # التحقق من وجود رقم في الأمر
    if command_text.startswith('/email') and len(command_text) > 6:
        try:
            count = int(command_text[6:])  # استخراج الرقم بعد /email
            if count <= 0 or count > 100:  # حد أقصى 100 إيميل
                await update.message.reply_text("❌ العدد يجب أن يكون بين 1 و 100")
                return
        except ValueError:
            await update.message.reply_text("❌ صيغة الأمر غير صحيحة. استخدم /email أو /email50 مثلاً")
            return

    # التحقق من الكريدت
    if not bot_instance.check_user_credits(user_id, count):
        user_credits = bot_instance.user_db.get_credits(user_id)
        await update.message.reply_text(
            f"❌ **رصيدك غير كافي!**\n\n"
            f"💰 رصيدك الحالي: {user_credits} كريدت\n"
            f"💳 المطلوب: {count} كريدت\n\n"
            f"📞 **للحصول على كريدت:**\n"
            f"💬 تلقرام: @{bot_instance.admin_username}\n"
            f"📱 واتساب: {bot_instance.admin_phone}",
            parse_mode='Markdown'
        )
        return

    # إرسال رسالة انتظار
    if count == 1:
        waiting_message = await update.message.reply_text("🔍 جاري البحث عن حساب شات جي بي تي متاح...")
    else:
        waiting_message = await update.message.reply_text(f"🔍 جاري البحث عن {count} حساب شات جي بي تي متاح...")

    try:
        # الحصول على البيانات من الشيت
        if not bot_instance.sheet:
            await waiting_message.edit_text("❌ خطأ في الاتصال بـ Google Sheets")
            return

        # قراءة الأعمدة F, G, H (الإيميلات الجديدة)
        email_col = bot_instance.sheet.col_values(6)  # العمود F
        password_col = bot_instance.sheet.col_values(7)  # العمود G
        status_col = bot_instance.sheet.col_values(8)  # العمود H

        # التأكد من أن القوائم لها نفس الطول
        max_len = max(len(email_col), len(password_col), len(status_col))
        email_col.extend([''] * (max_len - len(email_col)))
        password_col.extend([''] * (max_len - len(password_col)))
        status_col.extend([''] * (max_len - len(status_col)))

        # فلترة الإيميلات المتاحة (التي لا تحتوي على حالة في العمود H)
        available_emails = []
        for i in range(1, len(email_col)):  # البداية من الصف 2 (index 1)
            if email_col[i].strip() and password_col[i].strip() and not status_col[i].strip():
                available_emails.append({
                    'row': i + 1,  # رقم الصف الفعلي في الشيت
                    'email': email_col[i].strip(),
                    'password': password_col[i].strip()
                })

        if len(available_emails) == 0:
            await waiting_message.edit_text(
                f"❌ عذراً، لا توجد حسابات شات جي بي تي متاحة حالياً.\n"
                f"⏰ يرجى المحاولة لاحقاً أو التواصل مع الإدارة."
            )
            return

        if len(available_emails) < count:
            # إعطاء الإيميلات المتاحة بدلاً من رفض الطلب
            await waiting_message.edit_text(
                f"⚠️ تم العثور على {len(available_emails)} حساب شات جي بي تي فقط من أصل {count} مطلوب.\n"
                f"✅ سيتم إعطاؤك جميع الحسابات المتاحة ({len(available_emails)} حساب)..."
            )
            count = len(available_emails)  # تحديث العدد للإيميلات المتاحة

        # أخذ العدد المطلوب من الإيميلات
        selected_emails = available_emails[:count]

        # تحديث حالة الإيميلات إلى "مُستخدم"
        user_info = f"@{username}" if username != "غير محدد" else f"User_{user_id}"
        timestamp = bot_instance.get_current_time()
        status_text = f"مُستخدم - {user_info} - {timestamp}"

        for email_data in selected_emails:
            bot_instance.sheet.update_cell(email_data['row'], 8, status_text)  # العمود H للحالة

        # إرسال الإيميلات للمستخدم
        if count == 1:
            email_data = selected_emails[0]
            # خصم الكريدت
            bot_instance.deduct_user_credits(user_id, 1)
            remaining_credits = bot_instance.user_db.get_credits(user_id)

            email_message = f"""
✅ تم العثور على حساب شات جي بي تي لك!

🤖 **حساب ChatGPT:** `{email_data['email']}`
🔐 **كلمة المرور:** `{email_data['password']}`

💰 **تم خصم 1 كريدت - رصيدك الحالي: {remaining_credits} كريدت**

⚠️ **ملاحظة مهمة:**
• هذا الحساب أصبح مُستخدم الآن ولن يُعطى لأحد آخر
• احفظ البيانات في مكان آمن
• لا تشارك هذه البيانات مع أحد

👤 **المستخدم:** {first_name} (@{username})
🆔 **معرف المستخدم:** `{user_id}`
🕐 **وقت الشراء:** {timestamp}
            """
            await waiting_message.edit_text(email_message, parse_mode='Markdown')
            logger.info(f"تم إعطاء إيميل للمستخدم {user_id} (@{username}) - {first_name}")
        else:
            # خصم الكريدت
            bot_instance.deduct_user_credits(user_id, len(selected_emails))
            remaining_credits = bot_instance.user_db.get_credits(user_id)

            # إنشاء رسالة الحسابات
            emails_text = ""
            for i, email_data in enumerate(selected_emails, 1):
                emails_text += f"\n**حساب {i}:**\n🤖 `{email_data['email']}`\n🔐 `{email_data['password']}`\n"

            emails_message = f"""
✅ تم العثور على {len(selected_emails)} حساب شات جي بي تي لك!

{emails_text}
💰 **تم خصم {len(selected_emails)} كريدت - رصيدك الحالي: {remaining_credits} كريدت**

⚠️ **ملاحظة مهمة:**
• هذه الحسابات أصبحت مُستخدمة الآن ولن تُعطى لأحد آخر
• احفظ البيانات في مكان آمن
• لا تشارك هذه البيانات مع أحد

👤 **المستخدم:** {first_name} (@{username})
🆔 **معرف المستخدم:** `{user_id}`
🕐 **وقت الشراء:** {timestamp}
            """
            await waiting_message.edit_text(emails_message, parse_mode='Markdown')
            logger.info(f"تم إعطاء {len(selected_emails)} إيميل للمستخدم {user_id} (@{username}) - {first_name}")

    except Exception as e:
        logger.error(f"خطأ في أمر شراء الإيميل: {e}")
        await waiting_message.edit_text("❌ حدث خطأ غير متوقع. يرجى المحاولة لاحقاً.")

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر عرض الكريدت"""
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    user_name = update.effective_user.first_name or "صديقي"

    # تحديث معلومات المستخدم
    bot_instance.user_db.update_user_info(user_id, username, user_name)

    # الحصول على بيانات المستخدم
    user_data, _ = bot_instance.user_db.get_user(user_id)
    credits = user_data["credits"]
    total_purchases = user_data["total_purchases"]
    join_date = user_data["join_date"][:10]  # أول 10 أحرف (التاريخ فقط)

    credits_message = f"""
💰 **معلومات رصيدك**

👤 **المستخدم:** {user_name}
🆔 **معرف المستخدم:** `{user_id}`
💳 **الرصيد الحالي:** {credits} كريدت
🛒 **إجمالي المشتريات:** {total_purchases}
📅 **تاريخ الانضمام:** {join_date}

💡 **ملاحظة:** كل حساب يوتيوب أو شات جي بي تي يكلف 1 كريدت

📞 **للحصول على كريدت:**
💬 **تلقرام:** @{bot_instance.admin_username}
📱 **واتساب:** {bot_instance.admin_phone}
    """

    await update.message.reply_text(credits_message, parse_mode='Markdown')

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر عرض معلومات التواصل"""
    contact_message = f"""
📞 **معلومات التواصل مع الإدارة**

👤 **الأدمن:** {bot_instance.admin_username}

📱 **طرق التواصل:**
💬 **تلقرام:** @{bot_instance.admin_username}
📞 **واتساب:** {bot_instance.admin_phone}

🎯 **يمكنك التواصل للحصول على:**
• كريدت إضافي للشراء
• حل المشاكل التقنية
• الاستفسارات العامة
• طلبات خاصة

⏰ **أوقات الرد:**
• متاح معظم أوقات اليوم
• الرد خلال ساعات قليلة عادة

💡 **نصيحة:** استخدم واتساب للرد السريع!
    """

    await update.message.reply_text(contact_message, parse_mode='Markdown')

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر عرض معلومات التواصل"""
    contact_message = f"""
📞 **معلومات التواصل مع الإدارة**

👤 **الأدمن:** {bot_instance.admin_username}

📱 **طرق التواصل:**
💬 **تلقرام:** @{bot_instance.admin_username}
📞 **واتساب:** {bot_instance.admin_phone}

🎯 **يمكنك التواصل للحصول على:**
• كريدت إضافي للشراء
• حل المشاكل التقنية
• الاستفسارات العامة
• طلبات خاصة

⏰ **أوقات الرد:**
• متاح معظم أوقات اليوم
• الرد خلال ساعات قليلة عادة

💡 **نصيحة:** استخدم واتساب للرد السريع!
    """

    await update.message.reply_text(contact_message, parse_mode='Markdown')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر لوحة تحكم الأدمن - عرض جميع الصلاحيات والأوامر"""
    username = update.effective_user.username or ""
    user_id = update.effective_user.id

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username, user_id):
        await update.message.reply_text(
            "❌ **غير مسموح!**\n\n"
            "هذا الأمر متاح للأدمن فقط.\n"
            f"📞 للتواصل مع الأدمن: @{bot_instance.admin_username}",
            parse_mode='Markdown'
        )
        return

    # الحصول على إحصائيات سريعة
    try:
        stats = bot_instance.get_stats()
        all_users = bot_instance.user_db.get_all_users()
        total_users = len(all_users)

        # حساب إجمالي الكريدت
        total_credits = 0
        for user_id in all_users:
            total_credits += bot_instance.user_db.get_credits(int(user_id))

        admin_panel = f"""
👑 **لوحة تحكم الأدمن**

🎯 **معلومات سريعة:**
👥 **إجمالي المستخدمين:** {total_users}
💰 **إجمالي الكريدت:** {total_credits}
📺 **حسابات يوتيوب متاحة:** {stats['available_accounts']}
🤖 **حسابات شات جي بي تي متاحة:** {stats['available_emails']}

💳 **أوامر إدارة الكريدت:**
• `/addcredits [user_id] [amount]` - إضافة كريدت مخصص
• `/give100 [user_id]` - إعطاء 100 كريدت لمستخدم
• `/resetuser [user_id]` - تصفير كريدت مستخدم محدد
• `/resetall` - تصفير كريدت جميع المستخدمين
• `/resetallconfirm` - تأكيد التصفير الجماعي
• `/giveall100` - إعطاء 100 كريدت لجميع المستخدمين
• `/giveall100confirm` - تأكيد العملية الجماعية

📊 **أوامر الإحصائيات والإدارة:**
• `/adminstats` - إحصائيات مفصلة للأدمن
• `/allusers` - عرض جميع المستخدمين
• `/stats` - إحصائيات عامة للحسابات
• `/debug` - فحص البيانات (20 صف)
• `/debugall` - فحص جميع البيانات (100 صف)

📢 **أوامر التواصل:**
• `/broadcast [message]` - إرسال رسالة لجميع المستخدمين

🎯 **أوامر عامة:**
• `/admin` - هذه اللوحة
• `/help` - المساعدة العامة
• `/contact` - معلومات التواصل

📞 **معلومات التواصل:**
💬 **تلقرام:** @{bot_instance.admin_username}
📱 **واتساب:** {bot_instance.admin_phone}

💡 **أمثلة سريعة:**
• `/addcredits 123456789 50` - إضافة 50 كريدت
• `/give100 123456789` - إعطاء 100 كريدت
• `/broadcast مرحباً بجميع المستخدمين!` - رسالة جماعية
        """

        await update.message.reply_text(admin_panel, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في لوحة تحكم الأدمن: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ في تحميل لوحة التحكم.\n"
            "يرجى المحاولة لاحقاً أو استخدام الأوامر المنفصلة.",
            parse_mode='Markdown'
        )

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تشخيصي لفحص البيانات"""
    try:
        if not bot_instance.sheet:
            await update.message.reply_text("❌ خطأ في الاتصال بـ Google Sheets")
            return

        # قراءة الأعمدة مباشرة
        email_col = bot_instance.sheet.col_values(1)  # العمود A
        password_col = bot_instance.sheet.col_values(2)  # العمود B
        status_col = bot_instance.sheet.col_values(3)  # العمود C

        debug_message = f"""
🔍 **تشخيص البيانات:**

📊 **عدد الإيميلات في العمود A:** {len(email_col)}
📊 **عدد كلمات المرور في العمود B:** {len(password_col)}
📊 **عدد الحالات في العمود C:** {len(status_col)}

📋 **جميع البيانات من الأعمدة المباشرة:**
"""

        # عرض جميع البيانات
        max_len = max(len(email_col), len(password_col), len(status_col))

        # عرض إحصائيات سريعة
        available_count = 0
        used_count = 0

        for i in range(1, max_len):  # تجاهل الصف الأول (العناوين)
            email = email_col[i].strip() if i < len(email_col) and email_col[i] else ''
            password = password_col[i].strip() if i < len(password_col) and password_col[i] else ''
            status = status_col[i].strip() if i < len(status_col) and status_col[i] else ''

            if email and password:
                if status:
                    used_count += 1
                else:
                    available_count += 1

        debug_message += f"""

📊 **الإحصائيات:**
🟢 متاح: {available_count}
🔴 مُستخدم: {used_count}
📈 المجموع: {available_count + used_count}

📋 **آخر 20 صف من البيانات:**
"""

        # عرض آخر 20 صف
        start_index = max(1, max_len - 20)  # البداية من آخر 20 صف أو من الصف 1
        for i in range(start_index, max_len):
            email = email_col[i] if i < len(email_col) else 'فارغ'
            password = password_col[i] if i < len(password_col) else 'فارغ'
            status = status_col[i] if i < len(status_col) else 'فارغ'

            # تقصير كلمة المرور للعرض
            display_password = password[:8] + "..." if len(password) > 8 else password
            display_status = status[:10] + "..." if len(status) > 10 else status

            debug_message += f"\nصف {i+1}: `{email}` | `{display_password}` | `{display_status}`"

        await update.message.reply_text(debug_message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في أمر التشخيص: {e}")
        await update.message.reply_text(f"❌ خطأ في التشخيص: {str(e)}")

async def debug_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تشخيصي لفحص جميع البيانات (حتى 100 صف)"""
    try:
        if not bot_instance.sheet:
            await update.message.reply_text("❌ خطأ في الاتصال بـ Google Sheets")
            return

        # قراءة الأعمدة مباشرة
        email_col = bot_instance.sheet.col_values(1)  # العمود A
        password_col = bot_instance.sheet.col_values(2)  # العمود B
        status_col = bot_instance.sheet.col_values(3)  # العمود C

        max_len = max(len(email_col), len(password_col), len(status_col))

        # تقسيم البيانات إلى رسائل متعددة (كل رسالة 30 صف)
        rows_per_message = 30
        total_messages = (max_len - 1 + rows_per_message - 1) // rows_per_message  # تقريب للأعلى

        for msg_num in range(total_messages):
            start_row = 1 + (msg_num * rows_per_message)  # تجاهل الصف الأول (العناوين)
            end_row = min(start_row + rows_per_message, max_len)

            debug_message = f"""
🔍 **البيانات الكاملة - الجزء {msg_num + 1}/{total_messages}**
📊 **الصفوف {start_row} إلى {end_row - 1} من أصل {max_len - 1}**

"""

            for i in range(start_row, end_row):
                email = email_col[i] if i < len(email_col) else 'فارغ'
                password = password_col[i] if i < len(password_col) else 'فارغ'
                status = status_col[i] if i < len(status_col) else 'فارغ'

                # تقصير البيانات للعرض
                display_email = email[:25] + "..." if len(email) > 25 else email
                display_password = password[:10] + "..." if len(password) > 10 else password
                display_status = status[:15] + "..." if len(status) > 15 else status

                debug_message += f"صف {i+1}: `{display_email}` | `{display_password}` | `{display_status}`\n"

            await update.message.reply_text(debug_message, parse_mode='Markdown')

            # توقف قصير بين الرسائل
            import asyncio
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"خطأ في أمر التشخيص الكامل: {e}")
        await update.message.reply_text(f"❌ خطأ في التشخيص: {str(e)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر عرض الإحصائيات"""
    try:
        stats = bot_instance.get_stats()

        stats_message = f"""
📊 **إحصائيات الحسابات**

🟢 **متاح:** {stats['available']} حساب
🔴 **مُستخدم:** {stats['used']} حساب
📈 **المجموع:** {stats['total']} حساب

📋 **معلومات إضافية:**
• آخر تحديث: {bot_instance.get_current_time()}
• حالة الاتصال: {"✅ متصل" if bot_instance.sheet else "❌ غير متصل"}
        """

        await update.message.reply_text(stats_message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في أمر الإحصائيات: {e}")
        await update.message.reply_text("❌ حدث خطأ في جلب الإحصائيات.")

async def add_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر إضافة كريدت (للأدمن فقط)"""
    username = update.effective_user.username or ""
    user_id = update.effective_user.id

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username, user_id):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        # استخراج المعاملات من الرسالة
        args = update.message.text.split()
        if len(args) != 3:
            await update.message.reply_text(
                "❌ **صيغة الأمر غير صحيحة!**\n\n"
                "📝 **الاستخدام الصحيح:**\n"
                "`/addcredits [user_id] [amount]`\n\n"
                "**مثال:**\n"
                "`/addcredits 123456789 10`",
                parse_mode='Markdown'
            )
            return

        target_user_id = int(args[1])
        amount = int(args[2])

        if amount <= 0:
            await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من صفر!")
            return

        # إضافة الكريدت
        new_balance = bot_instance.user_db.add_credits(target_user_id, amount)

        await update.message.reply_text(
            f"✅ **تم إضافة الكريدت بنجاح!**\n\n"
            f"👤 **معرف المستخدم:** `{target_user_id}`\n"
            f"💰 **المبلغ المضاف:** {amount} كريدت\n"
            f"💳 **الرصيد الجديد:** {new_balance} كريدت",
            parse_mode='Markdown'
        )

        logger.info(f"الأدمن {username} أضاف {amount} كريدت للمستخدم {target_user_id}")

    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال أرقام صحيحة!")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def give_100_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر إعطاء 100 كريدت لمستخدم (للأدمن فقط)"""
    username = update.effective_user.username or ""

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        # استخراج المعاملات من الرسالة
        args = update.message.text.split()
        if len(args) != 2:
            await update.message.reply_text(
                "❌ **صيغة الأمر غير صحيحة!**\n\n"
                "📝 **الاستخدام الصحيح:**\n"
                "`/give100 [user_id]`\n\n"
                "**مثال:**\n"
                "`/give100 123456789`\n\n"
                "💡 **سيتم إعطاء 100 كريدت للمستخدم تلقائياً**",
                parse_mode='Markdown'
            )
            return

        target_user_id = int(args[1])

        # إضافة 100 كريدت
        new_balance = bot_instance.user_db.add_credits(target_user_id, 100)

        # الحصول على معلومات المستخدم
        user_data = bot_instance.user_db.get_user(target_user_id)
        username_target = user_data.get('username', 'غير محدد')
        first_name_target = user_data.get('first_name', 'غير محدد')

        await update.message.reply_text(
            f"🎉 **تم إعطاء 100 كريدت بنجاح!**\n\n"
            f"👤 **المستخدم:** {first_name_target} (@{username_target})\n"
            f"🆔 **معرف المستخدم:** `{target_user_id}`\n"
            f"💰 **الكريدت المضاف:** 100 كريدت\n"
            f"💳 **الرصيد الجديد:** {new_balance} كريدت\n\n"
            f"✨ **هدية من الإدارة!**",
            parse_mode='Markdown'
        )

        # إرسال إشعار للمستخدم المستهدف
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **مبروك! لقد حصلت على هدية من الإدارة!**\n\n"
                     f"💰 **تم إضافة 100 كريدت لحسابك!**\n"
                     f"💳 **رصيدك الحالي:** {new_balance} كريدت\n\n"
                     f"🛒 **يمكنك الآن شراء 100 حساب Gmail!**\n"
                     f"📱 استخدم `/buy` لشراء حساب أو `/credits` لعرض رصيدك",
                parse_mode='Markdown'
            )
            await update.message.reply_text("✅ تم إرسال إشعار للمستخدم أيضاً!")
        except Exception:
            await update.message.reply_text("⚠️ تم إضافة الكريدت ولكن لم يتم إرسال الإشعار للمستخدم")

        logger.info(f"الأدمن {username} أعطى 100 كريدت للمستخدم {target_user_id}")

    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال معرف مستخدم صحيح!")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر إرسال رسالة لجميع المستخدمين (للأدمن فقط)"""
    username = update.effective_user.username or ""

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        # استخراج الرسالة
        message_text = update.message.text.replace('/broadcast', '').strip()

        if not message_text:
            await update.message.reply_text(
                "❌ **يرجى كتابة الرسالة!**\n\n"
                "📝 **الاستخدام الصحيح:**\n"
                "`/broadcast رسالتك هنا`\n\n"
                "**مثال:**\n"
                "`/broadcast مرحباً بجميع المستخدمين!`",
                parse_mode='Markdown'
            )
            return

        # الحصول على جميع المستخدمين
        all_users = bot_instance.user_db.get_all_users()

        if not all_users:
            await update.message.reply_text("❌ لا يوجد مستخدمين في قاعدة البيانات!")
            return

        # إرسال رسالة التأكيد
        confirm_message = await update.message.reply_text(
            f"📢 **بدء إرسال الرسالة لـ {len(all_users)} مستخدم...**"
        )

        # إرسال الرسالة لجميع المستخدمين
        success_count = 0
        failed_count = 0

        broadcast_message = f"📢 **رسالة من الإدارة:**\n\n{message_text}"

        for user_id in all_users:
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=broadcast_message,
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception:
                failed_count += 1

        # تحديث رسالة التأكيد
        await confirm_message.edit_text(
            f"✅ **تم إرسال الرسالة!**\n\n"
            f"📊 **الإحصائيات:**\n"
            f"✅ نجح: {success_count}\n"
            f"❌ فشل: {failed_count}\n"
            f"📱 إجمالي: {len(all_users)}",
            parse_mode='Markdown'
        )

        logger.info(f"الأدمن {username} أرسل رسالة جماعية لـ {success_count} مستخدم")

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def give_all_100_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر إعطاء 100 كريدت لجميع المستخدمين (للأدمن فقط)"""
    username = update.effective_user.username or ""

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        # الحصول على جميع المستخدمين
        all_users = bot_instance.user_db.get_all_users()

        if not all_users:
            await update.message.reply_text("❌ لا يوجد مستخدمين في قاعدة البيانات!")
            return

        # رسالة تأكيد
        confirm_message = await update.message.reply_text(
            f"⚠️ **تأكيد العملية**\n\n"
            f"🎯 **ستقوم بإعطاء 100 كريدت لـ {len(all_users)} مستخدم**\n"
            f"💰 **إجمالي الكريدت المضاف:** {len(all_users) * 100} كريدت\n\n"
            f"📝 **اكتب 'نعم' للتأكيد أو أي شيء آخر للإلغاء**",
            parse_mode='Markdown'
        )

        # انتظار رد المستخدم (محاكاة - في التطبيق الحقيقي نحتاج conversation handler)
        await update.message.reply_text(
            "💡 **لتنفيذ العملية مباشرة، استخدم الأمر:**\n"
            "`/giveall100confirm`",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def give_all_100_credits_confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد إعطاء 100 كريدت لجميع المستخدمين"""
    username = update.effective_user.username or ""

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        # الحصول على جميع المستخدمين
        all_users = bot_instance.user_db.get_all_users()

        if not all_users:
            await update.message.reply_text("❌ لا يوجد مستخدمين في قاعدة البيانات!")
            return

        # رسالة بداية العملية
        progress_message = await update.message.reply_text(
            f"🚀 **بدء إعطاء 100 كريدت لـ {len(all_users)} مستخدم...**"
        )

        # إعطاء 100 كريدت لكل مستخدم
        success_count = 0
        failed_count = 0

        for user_id in all_users:
            try:
                bot_instance.user_db.add_credits(int(user_id), 100)
                success_count += 1

                # إرسال إشعار للمستخدم
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🎉 **مبروك! هدية من الإدارة!**\n\n"
                             f"💰 **تم إضافة 100 كريدت لحسابك!**\n"
                             f"🛒 **يمكنك الآن شراء 100 حساب Gmail!**\n\n"
                             f"📱 استخدم `/buy` لشراء حساب أو `/credits` لعرض رصيدك",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass  # تجاهل أخطاء الإرسال

            except Exception:
                failed_count += 1

        # تحديث رسالة التقدم
        await progress_message.edit_text(
            f"✅ **تمت العملية بنجاح!**\n\n"
            f"📊 **النتائج:**\n"
            f"✅ نجح: {success_count} مستخدم\n"
            f"❌ فشل: {failed_count} مستخدم\n"
            f"💰 **إجمالي الكريدت المضاف:** {success_count * 100} كريدت\n"
            f"📱 **إجمالي المستخدمين:** {len(all_users)}",
            parse_mode='Markdown'
        )

        logger.info(f"الأدمن {username} أعطى 100 كريدت لـ {success_count} مستخدم")

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def show_all_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر عرض جميع المستخدمين (للأدمن فقط)"""
    username = update.effective_user.username or ""
    user_id = update.effective_user.id

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username, user_id):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        all_users = bot_instance.user_db.get_all_users()

        if not all_users:
            await update.message.reply_text("❌ لا يوجد مستخدمين في قاعدة البيانات!")
            return

        # إحصائيات سريعة
        total_users = len(all_users)
        total_credits = sum(user.get('credits', 0) for user in all_users.values())
        users_with_credits = sum(1 for user in all_users.values() if user.get('credits', 0) > 0)

        message = f"👥 **جميع مستخدمي البوت ({total_users} مستخدم)**\n\n"
        message += f"💰 **إجمالي الكريدت:** {total_credits}\n"
        message += f"💳 **مستخدمين لديهم كريدت:** {users_with_credits}\n\n"

        # عرض تفاصيل كل مستخدم
        for i, (user_id, user_data) in enumerate(all_users.items(), 1):
            credits = user_data.get('credits', 0)
            username_user = user_data.get('username', 'غير محدد')
            first_name = user_data.get('first_name', 'غير محدد')
            total_purchases = user_data.get('total_purchases', 0)

            message += f"**{i}.** {first_name}\n"
            message += f"   📱 @{username_user}\n"
            message += f"   🆔 `{user_id}`\n"
            message += f"   💰 {credits} كريدت\n"
            message += f"   🛒 {total_purchases} مشتريات\n\n"

            # تقسيم الرسالة إذا كانت طويلة
            if len(message) > 3500:
                await update.message.reply_text(message, parse_mode='Markdown')
                message = ""

        if message:
            await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في عرض المستخدمين: {str(e)}")

async def reset_all_users_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تصفير كريدت جميع المستخدمين (للأدمن فقط)"""
    username = update.effective_user.username or ""
    user_id = update.effective_user.id

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username, user_id):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        all_users = bot_instance.user_db.get_all_users()

        if not all_users:
            await update.message.reply_text("❌ لا يوجد مستخدمين في قاعدة البيانات!")
            return

        # حساب المستخدمين الذين لديهم كريدت
        users_with_credits = []
        total_credits = 0

        for user_id, user_data in all_users.items():
            credits = user_data.get('credits', 0)
            if credits > 0:
                users_with_credits.append({
                    'user_id': user_id,
                    'credits': credits,
                    'name': user_data.get('first_name', 'غير محدد')
                })
                total_credits += credits

        if not users_with_credits:
            await update.message.reply_text("✅ جميع المستخدمين لديهم 0 كريدت بالفعل!")
            return

        # رسالة تأكيد
        confirm_message = f"⚠️ **تأكيد تصفير الكريدت**\n\n"
        confirm_message += f"👥 **عدد المستخدمين:** {len(users_with_credits)}\n"
        confirm_message += f"💰 **إجمالي الكريدت:** {total_credits}\n\n"
        confirm_message += "**المستخدمين الذين سيتم تصفيرهم:**\n"

        for user in users_with_credits[:10]:  # عرض أول 10 فقط
            confirm_message += f"• {user['name']}: {user['credits']} كريدت\n"

        if len(users_with_credits) > 10:
            confirm_message += f"• ... و {len(users_with_credits) - 10} مستخدم آخر\n"

        confirm_message += f"\n💡 **استخدم `/resetallconfirm` للتأكيد**"

        await update.message.reply_text(confirm_message, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")

async def reset_all_users_credits_confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد تصفير كريدت جميع المستخدمين"""
    username = update.effective_user.username or ""
    user_id = update.effective_user.id

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username, user_id):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        all_users = bot_instance.user_db.get_all_users()

        # تصفير جميع المستخدمين
        reset_count = 0
        total_reset_credits = 0

        for user_id, user_data in all_users.items():
            credits = user_data.get('credits', 0)
            if credits > 0:
                bot_instance.user_db.set_credits(user_id, 0)
                reset_count += 1
                total_reset_credits += credits

        if reset_count == 0:
            await update.message.reply_text("✅ جميع المستخدمين لديهم 0 كريدت بالفعل!")
        else:
            await update.message.reply_text(
                f"🎉 **تم تصفير الكريدت بنجاح!**\n\n"
                f"👥 **المستخدمين المصفرين:** {reset_count}\n"
                f"💰 **الكريدت المصفر:** {total_reset_credits}\n"
                f"✅ **جميع المستخدمين الآن لديهم 0 كريدت!**",
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")

async def reset_user_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تصفير كريدت مستخدم محدد (للأدمن فقط)"""
    username = update.effective_user.username or ""
    user_id = update.effective_user.id

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username, user_id):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        # استخراج المعاملات من الرسالة
        args = update.message.text.split()
        if len(args) != 2:
            await update.message.reply_text(
                "❌ **صيغة الأمر غير صحيحة!**\n\n"
                "📝 **الاستخدام الصحيح:**\n"
                "`/resetuser [user_id]`\n\n"
                "**مثال:**\n"
                "`/resetuser 123456789`\n\n"
                "💡 **سيتم تصفير كريدت المستخدم إلى 0**",
                parse_mode='Markdown'
            )
            return

        target_user_id = int(args[1])

        # التحقق من وجود المستخدم
        all_users = bot_instance.user_db.get_all_users()
        target_user_id_str = str(target_user_id)

        if target_user_id_str not in all_users:
            await update.message.reply_text(
                f"❌ **المستخدم غير موجود!**\n\n"
                f"🆔 **معرف المستخدم:** `{target_user_id}`\n"
                f"📋 **استخدم `/allusers` لرؤية جميع المستخدمين**",
                parse_mode='Markdown'
            )
            return

        # الحصول على معلومات المستخدم
        user_data = all_users[target_user_id_str]
        old_credits = user_data.get('credits', 0)
        username_target = user_data.get('username', 'غير محدد')
        first_name_target = user_data.get('first_name', 'غير محدد')

        if old_credits == 0:
            await update.message.reply_text(
                f"✅ **المستخدم لديه 0 كريدت بالفعل!**\n\n"
                f"👤 **المستخدم:** {first_name_target} (@{username_target})\n"
                f"🆔 **معرف المستخدم:** `{target_user_id}`\n"
                f"💰 **الكريدت الحالي:** {old_credits} كريدت",
                parse_mode='Markdown'
            )
            return

        # تصفير الكريدت
        bot_instance.user_db.set_credits(target_user_id, 0)

        await update.message.reply_text(
            f"🎉 **تم تصفير الكريدت بنجاح!**\n\n"
            f"👤 **المستخدم:** {first_name_target} (@{username_target})\n"
            f"🆔 **معرف المستخدم:** `{target_user_id}`\n"
            f"💰 **الكريدت السابق:** {old_credits} كريدت\n"
            f"💳 **الكريدت الجديد:** 0 كريدت\n\n"
            f"✨ **تم التصفير بواسطة الأدمن!**",
            parse_mode='Markdown'
        )

        # إرسال إشعار للمستخدم المستهدف
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"⚠️ **إشعار من الإدارة**\n\n"
                     f"💰 **تم تصفير كريدتك بواسطة الأدمن**\n"
                     f"💳 **رصيدك الحالي:** 0 كريدت\n\n"
                     f"📞 **للاستفسار تواصل مع الإدارة:**\n"
                     f"💬 **تلقرام:** @{bot_instance.admin_username}\n"
                     f"📱 **واتساب:** {bot_instance.admin_phone}",
                parse_mode='Markdown'
            )
            await update.message.reply_text("✅ تم إرسال إشعار للمستخدم أيضاً!")
        except Exception:
            await update.message.reply_text("⚠️ تم تصفير الكريدت ولكن لم يتم إرسال الإشعار للمستخدم")

        logger.info(f"الأدمن {username} صفر كريدت المستخدم {target_user_id} من {old_credits} إلى 0")

    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال معرف مستخدم صحيح!")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر إحصائيات الأدمن"""
    username = update.effective_user.username or ""

    # التحقق من صلاحيات الأدمن
    if not bot_instance.is_admin(username):
        await update.message.reply_text("❌ هذا الأمر متاح للأدمن فقط!")
        return

    try:
        # إحصائيات المستخدمين
        user_stats = bot_instance.user_db.get_stats()

        # إحصائيات الحسابات
        account_stats = bot_instance.get_stats()

        admin_message = f"""
👑 **إحصائيات الأدمن**

👥 **المستخدمين:**
• إجمالي المستخدمين: {user_stats['total_users']}
• المستخدمين النشطين: {user_stats['active_users']}
• المستخدمين المحظورين: {user_stats['banned_users']}
• إجمالي المشتريات: {user_stats['total_purchases']}
• إجمالي الكريدت: {user_stats['total_credits']}

📧 **الحسابات:**
• إجمالي الحسابات: {account_stats['total_accounts']}
• الحسابات المتاحة: {account_stats['available_accounts']}
• الحسابات المستخدمة: {account_stats['used_accounts']}

📊 **معدل الاستخدام:** {account_stats['usage_percentage']:.1f}%
        """

        await update.message.reply_text(admin_message, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

def main():
    """تشغيل البوت"""
    global bot_instance
    bot_instance = TelegramAccountBot()

    if not bot_instance.bot_token:
        logger.error("لم يتم العثور على رمز البوت. تأكد من ملف .env")
        return

    # إنشاء التطبيق
    application = Application.builder().token(bot_instance.bot_token).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("buy", buy_account))
    application.add_handler(CommandHandler("email", buy_email))
    application.add_handler(CommandHandler("credits", credits_command))
    application.add_handler(CommandHandler("contact", contact_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CommandHandler("debugall", debug_all_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # أوامر الأدمن
    application.add_handler(CommandHandler("addcredits", add_credits_command))
    application.add_handler(CommandHandler("give100", give_100_credits_command))
    application.add_handler(CommandHandler("giveall100", give_all_100_credits_command))
    application.add_handler(CommandHandler("giveall100confirm", give_all_100_credits_confirm_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("adminstats", admin_stats_command))
    application.add_handler(CommandHandler("allusers", show_all_users_command))
    application.add_handler(CommandHandler("resetall", reset_all_users_credits_command))
    application.add_handler(CommandHandler("resetallconfirm", reset_all_users_credits_confirm_command))
    application.add_handler(CommandHandler("resetuser", reset_user_credits_command))

    # تشغيل البوت
    logger.info("تم تشغيل البوت...")
    print("🤖 البوت يعمل الآن...")
    print("📱 يمكنك اختبار البوت في تلقرام")
    print("⏹️ اضغط Ctrl+C لإيقاف البوت")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت بواسطة المستخدم")
        print("\n👋 تم إيقاف البوت بنجاح")

if __name__ == '__main__':
    main()
