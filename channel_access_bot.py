import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import sqlite3
from datetime import datetime, timedelta
import os
import json
import csv
from io import StringIO, BytesIO
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройки из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CARD_NUMBER = os.getenv("CARD_NUMBER")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "l_kz_kz_l")

# Проверка что все переменные загружены
if not BOT_TOKEN or not CARD_NUMBER or not ADMIN_ID:
    raise ValueError("❌ Ошибка: Не все переменные окружения установлены! Проверьте файл .env")

# VIP конфигурация
VIP_CONFIGS = {
    "vip1": {
        "name": "VIP 1",
        "emoji": "🥉",
        "price": "1500 ₸",
        "price_num": 1500,
        "channel_id": -1003561182205,
        "description": "Базовый VIP доступ",
        "enabled": True,
        "preview_description": "🎯 Что входит в VIP 1:\n\n• Эксклюзивный контент\n• Ранний доступ к новостям\n• Закрытые обсуждения\n• Бонусные материалы",
        "preview_images": []
    },
    "vip2": {
        "name": "VIP 2",
        "emoji": "🥈",
        "price": "2000 ₸",
        "price_num": 2000,
        "channel_id": -1003750922449,
        "description": "Расширенный VIP доступ",
        "enabled": True,
        "preview_description": "🎯 Что входит в VIP 2:\n\n• Всё из VIP 1\n• Премиум контент\n• Личные консультации\n• VIP-поддержка 24/7",
        "preview_images": []
    },
    "vip3": {
        "name": "VIP 3",
        "emoji": "🥇",
        "price": "2500 ₸",
        "price_num": 2500,
        "channel_id": -1003757283642,
        "description": "Премиум VIP доступ",
        "enabled": True,
        "preview_description": "🎯 Что входит в VIP 3:\n\n• Всё из VIP 2\n• Эксклюзивные вебинары\n• Приватные встречи\n• Уникальные материалы",
        "preview_images": []
    },
    "vip4": {
        "name": "VIP 4",
        "emoji": "💎",
        "price": "3000 ₸",
        "price_num": 3000,
        "channel_id": -1003702842443,
        "description": "Элитный VIP доступ",
        "enabled": True,
        "preview_description": "🎯 Что входит в VIP 4:\n\n• Всё из VIP 3\n• Персональный менеджер\n• Эксклюзивные ивенты\n• Максимальный приоритет",
        "preview_images": []
    },
    "vip5": {
        "name": "VIP 5",
        "emoji": "👑",
        "price": "3500 ₸",
        "price_num": 3500,
        "channel_id": -1003568736810,
        "description": "Максимальный VIP доступ",
        "enabled": True,
        "preview_description": "🎯 Что входит в VIP 5:\n\n• Всё из VIP 4\n• VIP статус навсегда\n• Индивидуальный подход\n• Закрытые привилегии",
        "preview_images": []
    }
}

# Путь к базе данных
DB_PATH = os.path.expanduser("~/bot_database.db")

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
BROADCAST_MESSAGE, PROMO_CODE, PROMO_DISCOUNT, SEARCH_USER = range(4)

# ==================== БАЗА ДАННЫХ ====================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Таблица users
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    old_users_exists = c.fetchone()
    
    if old_users_exists:
        c.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'vip_type' not in columns:
            logger.info("Migrating old database to new structure...")
            c.execute('''CREATE TABLE users_new
                         (user_id INTEGER,
                          vip_type TEXT,
                          username TEXT,
                          full_name TEXT,
                          payment_date TEXT,
                          invite_link TEXT,
                          status TEXT,
                          PRIMARY KEY (user_id, vip_type))''')
            c.execute('''INSERT INTO users_new 
                         SELECT user_id, 'vip1', username, full_name, payment_date, invite_link, status 
                         FROM users''')
            c.execute("DROP TABLE users")
            c.execute("ALTER TABLE users_new RENAME TO users")
            logger.info("Users table migrated successfully!")
    else:
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER,
                      vip_type TEXT,
                      username TEXT,
                      full_name TEXT,
                      payment_date TEXT,
                      invite_link TEXT,
                      status TEXT,
                      PRIMARY KEY (user_id, vip_type))''')
    
    # Таблица pending_payments
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_payments'")
    old_pending_exists = c.fetchone()
    
    if old_pending_exists:
        c.execute("PRAGMA table_info(pending_payments)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'vip_type' not in columns:
            logger.info("Migrating pending_payments table...")
            c.execute('''CREATE TABLE pending_payments_new
                         (user_id INTEGER,
                          vip_type TEXT,
                          username TEXT,
                          full_name TEXT,
                          request_date TEXT,
                          PRIMARY KEY (user_id, vip_type))''')
            c.execute('''INSERT INTO pending_payments_new 
                         SELECT user_id, 'vip1', username, full_name, request_date 
                         FROM pending_payments''')
            c.execute("DROP TABLE pending_payments")
            c.execute("ALTER TABLE pending_payments_new RENAME TO pending_payments")
            logger.info("Pending_payments table migrated successfully!")
    else:
        c.execute('''CREATE TABLE IF NOT EXISTS pending_payments
                     (user_id INTEGER,
                      vip_type TEXT,
                      username TEXT,
                      full_name TEXT,
                      request_date TEXT,
                      PRIMARY KEY (user_id, vip_type))''')
    
    # Таблица активности пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS user_activity
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  full_name TEXT,
                  first_start TEXT,
                  last_activity TEXT)''')
    
    # Таблица промокодов
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes
                 (code TEXT PRIMARY KEY,
                  discount INTEGER,
                  uses_left INTEGER,
                  created_date TEXT,
                  valid_until TEXT)''')
    
    # Таблица использованных промокодов
    c.execute('''CREATE TABLE IF NOT EXISTS promo_usage
                 (user_id INTEGER,
                  code TEXT,
                  used_date TEXT,
                  PRIMARY KEY (user_id, code))''')
    
    # Таблица забаненных пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS banned_users
                 (user_id INTEGER PRIMARY KEY,
                  ban_date TEXT,
                  reason TEXT)''')
    
    # Таблица логов действий
    c.execute('''CREATE TABLE IF NOT EXISTS action_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  action TEXT,
                  details TEXT,
                  timestamp TEXT)''')
    
    # Таблица отзывов
    c.execute('''CREATE TABLE IF NOT EXISTS reviews
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  full_name TEXT,
                  rating INTEGER,
                  comment TEXT,
                  created_date TEXT)''')
    
    # Таблица настроек
    c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    
    # Таблица текстов бота
    c.execute('''CREATE TABLE IF NOT EXISTS bot_texts
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    
    # Инициализация настроек по умолчанию
    c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('card_number', ?)", (CARD_NUMBER,))
    c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('daily_reports', 'enabled')")
    c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('payment_reminders', 'enabled')")
    
    # Инициализация текстов по умолчанию
    default_texts = {
        'welcome_user': '👋 Добро пожаловать, {name}!\n\n🔐 Этот бот продаёт доступ к приватным VIP каналам.\n\n💎 У нас 5 VIP уровней на выбор!\n\nНажмите \'Цены / Прайс\' чтобы посмотреть все варианты!',
        'payment_instruction': '💳 Инструкция по оплате:\n\n1️⃣ Переведите {price} на карту:\n{card}\n\n2️⃣ Сделайте скриншот или чек оплаты\n\n3️⃣ Отправьте чек боту:\n   📸 Скриншот (фото)\n   📄 PDF файл\n   📎 Любой документ\n\n⏳ После проверки платежа (обычно 1-5 минут) вы получите персональную ссылку на канал!\n\n📝 Важно: отправьте подтверждение оплаты в любом формате!',
        'payment_success': '✅ Оплата подтверждена!\n\n{vip_emoji} {vip_name}\n\n🎉 Ваша персональная ссылка на канал:\n{link}\n\n⚠️ Важно:\n- Ссылка работает только для вас\n- Не передавайте её другим\n- Доступ навсегда\n\nПриятного просмотра! 🔥',
        'info_text': 'ℹ️ Информация о VIP каналах:\n\n🔐 Приватные каналы с эксклюзивным контентом\n\n💎 5 VIP уровней на выбор\n\n✅ Доступ: Навсегда\n🔗 Персональная ссылка только для вас\n\n📞 Поддержка: нажмите кнопку ниже',
        'support_text': '📞 Поддержка:\n\nЕсли у вас возникли вопросы или проблемы:\n\n1. Напишите администратору\n2. Опишите вашу проблему\n3. Мы ответим в ближайшее время!'
    }
    
    for key, value in default_texts.items():
        c.execute("INSERT OR IGNORE INTO bot_texts VALUES (?, ?)", (key, value))
    
    # Инициализация текстов по умолчанию
    c.execute("INSERT OR IGNORE INTO bot_texts VALUES ('welcome_message', '👋 Добро пожаловать, {name}!\n\n🔐 Этот бот продаёт доступ к приватным VIP каналам.\n\n💎 У нас 5 VIP уровней на выбор!\n\nНажмите ''Цены / Прайс'' чтобы посмотреть все варианты!')")
    c.execute("INSERT OR IGNORE INTO bot_texts VALUES ('payment_instruction', '💳 Инструкция по оплате:\n\n1️⃣ Переведите {price} на карту:\n{card}\n\n2️⃣ Сделайте скриншот или чек оплаты\n\n3️⃣ Отправьте чек боту:\n   📸 Скриншот (фото)\n   📄 PDF файл\n   📎 Любой документ\n\n⏳ После проверки платежа (обычно 1-5 минут) вы получите персональную ссылку на канал!\n\n📝 Важно: отправьте подтверждение оплаты в любом формате!')")
    c.execute("INSERT OR IGNORE INTO bot_texts VALUES ('purchase_success', '✅ Оплата подтверждена!\n\n{vip_emoji} {vip_name}\n\n🎉 Ваша персональная ссылка на канал:\n{link}\n\n⚠️ Важно:\n- Ссылка работает только для вас\n- Не передавайте её другим\n- Доступ навсегда\n\nПриятного просмотра! 🔥')")
    c.execute("INSERT OR IGNORE INTO bot_texts VALUES ('info_message', 'ℹ️ Информация о VIP каналах:\n\n🔐 Приватные каналы с эксклюзивным контентом\n\n💎 5 VIP уровней на выбор\n\n✅ Доступ: Навсегда\n🔗 Персональная ссылка только для вас\n\n📞 Поддержка: нажмите кнопку ниже')")
    c.execute("INSERT OR IGNORE INTO bot_texts VALUES ('support_message', '📞 Поддержка:\n\nЕсли у вас возникли вопросы или проблемы:\n\n1. Напишите администратору\n2. Опишите вашу проблему\n3. Мы ответим в ближайшее время!')")
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at: {DB_PATH}")

# Функция для обновления активности пользователя
def update_user_activity(user_id, username, full_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("SELECT * FROM user_activity WHERE user_id=?", (user_id,))
    existing = c.fetchone()
    
    if existing:
        c.execute("UPDATE user_activity SET last_activity=?, username=?, full_name=? WHERE user_id=?",
                  (current_time, username or "Нет username", full_name or "Пользователь", user_id))
    else:
        c.execute("INSERT INTO user_activity VALUES (?, ?, ?, ?, ?)",
                  (user_id, username or "Нет username", full_name or "Пользователь", current_time, current_time))
    
    conn.commit()
    conn.close()

# Функция логирования действий
def log_action(user_id, action, details=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO action_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action, details, timestamp))
    conn.commit()
    conn.close()

# Проверка бана
def is_banned(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
    banned = c.fetchone()
    conn.close()
    result = banned is not None
    if result:
        logger.info(f"User {user_id} is BANNED - blocking access")
    return result

# Получить настройку
def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# Установить настройку
def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_settings VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# Получить текст
def get_text(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_texts WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""

# Установить текст
def set_text(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_texts VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# Получить текст бота
def get_bot_text(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_texts WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# Установить текст бота
def set_bot_text(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_texts VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# Сохранить VIP конфигурацию в настройки
def save_vip_config():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    import json
    c.execute("INSERT OR REPLACE INTO bot_settings VALUES ('vip_configs', ?)", (json.dumps(VIP_CONFIGS, ensure_ascii=False),))
    conn.commit()
    conn.close()

# Загрузить VIP конфигурацию из настроек
def load_vip_config():
    global VIP_CONFIGS
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_settings WHERE key='vip_configs'")
    result = c.fetchone()
    conn.close()
    if result:
        import json
        loaded_configs = json.loads(result[0])
        
        # Добавляем новые поля если их нет
        for vip_key, vip_data in loaded_configs.items():
            if 'preview_images' not in vip_data:
                vip_data['preview_images'] = []
            if 'preview_description' not in vip_data:
                vip_data['preview_description'] = vip_data.get('description', 'VIP доступ')
        
        VIP_CONFIGS = loaded_configs
        logger.info("✅ VIP конфиги загружены из БД")

# ==================== ГЛАВНОЕ МЕНЮ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    logger.info(f"User {user.id} ({user.username}) executed /start")
    
    # Проверка бана
    if is_banned(user.id):
        logger.warning(f"BLOCKED: User {user.id} is banned, denying access")
        keyboard = [[InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ Вы заблокированы и не можете использовать бот.\n\nЕсли считаете это ошибкой, обратитесь в поддержку.", reply_markup=reply_markup)
        return
    
    logger.info(f"User {user.id} passed ban check, showing menu")
    
    # Обновляем активность
    update_user_activity(user.id, user.username, user.first_name)
    log_action(user.id, "start", "Пользователь открыл бот")
    
    # Админ меню
    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users_menu")],
            [InlineKeyboardButton("📈 Активность", callback_data="admin_activity")],
            [InlineKeyboardButton("⏳ Ожидают проверки", callback_data="admin_pending")],
            [InlineKeyboardButton("💬 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promo")],
            [InlineKeyboardButton("✏️ Редактор бота", callback_data="admin_editor")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton("💾 Экспорт данных", callback_data="admin_export")],
            [InlineKeyboardButton("👤 Режим пользователя", callback_data="user_mode")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        welcome_text = "🔐 АДМИН-ПАНЕЛЬ\n\nВыберите действие:"
        
        if update.message:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        else:
            if update.callback_query.message.photo or update.callback_query.message.document:
                await update.callback_query.message.delete()
                await context.bot.send_message(chat_id=user.id, text=welcome_text, reply_markup=reply_markup)
            else:
                await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)
        return
    
    # Обычное меню пользователя
    keyboard = [
        [InlineKeyboardButton("💰 Цены / Прайс", callback_data="prices")],
        [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
        [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="leave_review")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Получаем текст из БД
    welcome_text = get_bot_text('welcome_message')
    if welcome_text:
        welcome_text = welcome_text.replace('{name}', user.first_name)
    else:
        welcome_text = f"👋 Добро пожаловать, {user.first_name}!\n\n🔐 Этот бот продаёт доступ к приватным VIP каналам.\n\n💎 У нас 5 VIP уровней на выбор!\n\nНажмите 'Цены / Прайс' чтобы посмотреть все варианты!"
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        if update.callback_query.message.photo or update.callback_query.message.document:
            await update.callback_query.message.delete()
            await context.bot.send_message(chat_id=user.id, text=welcome_text, reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)

# ==================== ОБРАБОТЧИКИ КНОПОК ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    logger.info(f"Button pressed: {query.data} by user {query.from_user.id}")
    user = query.from_user
    
    # Проверка бана
    if is_banned(user.id) and not user.id == ADMIN_ID:
        logger.warning(f"BLOCKED: Banned user {user.id} tried to press button {query.data}")
        keyboard = [[InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("❌ Вы заблокированы и не можете использовать бот.\n\nЕсли считаете это ошибкой, обратитесь в поддержку.", reply_markup=reply_markup)
        return
    
    # Обновляем активность
    update_user_activity(user.id, user.username, user.first_name)
    
    # ========== ПОЛЬЗОВАТЕЛЬСКОЕ МЕНЮ ==========
    
    if query.data == "prices":
        keyboard = []
        for vip_key, vip_data in VIP_CONFIGS.items():
            if vip_data.get('enabled', True):
                keyboard.append([InlineKeyboardButton(
                    f"{vip_data['emoji']} {vip_data['name']} - {vip_data['price']}", 
                    callback_data=f"select_{vip_key}"
                )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        prices_text = "💰 ПРАЙС-ЛИСТ VIP ДОСТУПОВ\n\n"
        prices_text += "Выберите интересующий вас VIP уровень:\n\n"
        
        for vip_data in VIP_CONFIGS.values():
            if vip_data.get('enabled', True):
                prices_text += f"{vip_data['emoji']} {vip_data['name']} - {vip_data['price']}\n"
        
        prices_text += "\n✅ Доступ: Навсегда\n🔗 Персональная ссылка только для вас"
        await query.message.edit_text(prices_text, reply_markup=reply_markup)
    
    elif query.data.startswith("select_"):
        vip_key = query.data.replace("select_", "")
        vip_data = VIP_CONFIGS.get(vip_key)
        
        if not vip_data or not vip_data.get('enabled', True):
            keyboard = [[InlineKeyboardButton("◀️ К выбору VIP", callback_data="prices")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("❌ Этот VIP уровень временно недоступен.", reply_markup=reply_markup)
            return
        
        keyboard = [
            [InlineKeyboardButton("💳 Купить доступ", callback_data=f"buy_{vip_key}")],
            [InlineKeyboardButton("👁 Предпросмотр", callback_data=f"preview_{vip_key}")],
            [InlineKeyboardButton("🎁 У меня есть промокод", callback_data=f"use_promo_{vip_key}")],
            [InlineKeyboardButton("◀️ К выбору VIP", callback_data="prices")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        vip_info_text = f"{vip_data['emoji']} {vip_data['name']}\n\n"
        vip_info_text += f"📋 {vip_data['description']}\n\n"
        vip_info_text += f"💰 Цена: {vip_data['price']}\n"
        vip_info_text += f"✅ Доступ: Навсегда\n"
        vip_info_text += f"🔗 Персональная ссылка\n\n"
        vip_info_text += f"Нажмите 'Купить доступ' для оформления!"
        
        await query.message.edit_text(vip_info_text, reply_markup=reply_markup)
    
    elif query.data.startswith("preview_"):
        vip_key = query.data.replace("preview_", "")
        vip_data = VIP_CONFIGS.get(vip_key)
        
        if not vip_data or not vip_data.get('enabled', True):
            keyboard = [[InlineKeyboardButton("◀️ К выбору VIP", callback_data="prices")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("❌ Этот VIP уровень временно недоступен.", reply_markup=reply_markup)
            return
        
        # Получаем расширенное описание
        preview_desc = vip_data.get('preview_description', vip_data['description'])
        
        preview_text = f"👁 ПРЕДПРОСМОТР {vip_data['emoji']} {vip_data['name']}\n\n"
        preview_text += preview_desc
        preview_text += f"\n\n💰 Цена: {vip_data['price']}"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"select_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Проверяем есть ли скриншоты
        preview_images = vip_data.get('preview_images', [])
        
        if preview_images:
            # Если есть скриншоты - отправляем их
            await query.message.delete()
            
            # Отправляем каждый скриншот
            for i, file_id in enumerate(preview_images, 1):
                try:
                    await context.bot.send_photo(
                        chat_id=user.id, 
                        photo=file_id,
                        caption=f"📸 {i}/{len(preview_images)}"
                    )
                except Exception as e:
                    logger.error(f"Error sending preview image {file_id}: {e}")
            
            # Отправляем текст с кнопкой назад
            await context.bot.send_message(
                chat_id=user.id,
                text=preview_text,
                reply_markup=reply_markup
            )
        else:
            # Если скриншотов нет - просто текст
            await query.message.edit_text(
                preview_text + "\n\n📸 Скриншоты скоро будут добавлены!",
                reply_markup=reply_markup
            )
    
    elif query.data.startswith("buy_"):
        await handle_buy(query, context, user)
    
    elif query.data == "info":
        info_text = get_bot_text('info_message')
        if not info_text:
            info_text = "ℹ️ Информация о VIP каналах:\n\n"
            info_text += "🔐 Приватные каналы с эксклюзивным контентом\n\n"
            info_text += "💎 5 VIP уровней на выбор:\n"
            
            for vip_data in VIP_CONFIGS.values():
                if vip_data.get('enabled', True):
                    info_text += f"{vip_data['emoji']} {vip_data['name']} - {vip_data['price']}\n"
            
            info_text += "\n✅ Доступ: Навсегда\n"
            info_text += "🔗 Персональная ссылка только для вас\n\n"
            info_text += "📞 Поддержка: нажмите кнопку ниже"
        
        keyboard = [
            [InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(info_text, reply_markup=reply_markup)
    
    elif query.data == "support":
        # Принудительно читаем из базы при каждом запросе
        support_text = get_bot_text('support_message')
        logger.info(f"Support text from DB: {support_text[:50] if support_text else 'None'}...")
        
        if not support_text:
            support_text = "📞 Поддержка:\n\nЕсли у вас возникли вопросы или проблемы:\n\n1. Напишите администратору\n2. Опишите вашу проблему\n3. Мы ответим в ближайшее время!"
            logger.warning("Using default support text - DB returned None!")
        
        keyboard = [
            [InlineKeyboardButton("💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(support_text, reply_markup=reply_markup)
    
    elif query.data == "leave_review":
        keyboard = [
            [InlineKeyboardButton("⭐", callback_data="rate_1"), InlineKeyboardButton("⭐⭐", callback_data="rate_2")],
            [InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"), InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4")],
            [InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("⭐ Оцените бот:\n\nВыберите количество звёзд:", reply_markup=reply_markup)
    
    elif query.data.startswith("rate_"):
        rating = int(query.data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO reviews (user_id, username, full_name, rating, created_date) VALUES (?, ?, ?, ?, ?)",
                  (user.id, user.username or "Нет", user.first_name or "Пользователь", rating, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"✅ Спасибо за оценку! {'⭐' * rating}", reply_markup=reply_markup)
    
    elif query.data == "back":
        await start(update, context)
    
    elif query.data == "user_mode":
        keyboard = [
            [InlineKeyboardButton("💰 Цены / Прайс", callback_data="prices")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
            [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="leave_review")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
            [InlineKeyboardButton("🔙 Админ-панель", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("👋 Режим пользователя\n\n🔐 Этот бот продаёт доступ к приватным VIP каналам.\n\n💎 У нас 5 VIP уровней на выбор!", reply_markup=reply_markup)
    
    elif query.data == "admin_panel":
        await start(update, context)
    
    # ========== АДМИН МЕНЮ ==========
    
    elif query.data == "admin_stats":
        await show_admin_stats(query, context)
    
    elif query.data == "admin_users_menu":
        # Очищаем флаг поиска если был активен
        if 'searching_user' in context.user_data:
            context.user_data.pop('searching_user')
        
        keyboard = [
            [InlineKeyboardButton("👥 Список всех", callback_data="admin_users")],
            [InlineKeyboardButton("🔍 Поиск пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton("🚫 Управление банами", callback_data="admin_bans")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ\n\nВыберите действие:", reply_markup=reply_markup)
    
    elif query.data == "admin_users":
        await show_all_users(query, context)
    
    elif query.data == "admin_activity":
        await show_activity(query, context)
    
    elif query.data == "admin_pending":
        await show_pending(query, context)
    
    elif query.data == "admin_broadcast":
        keyboard = [
            [InlineKeyboardButton("📢 Рассылка всем", callback_data="broadcast_all")],
            [InlineKeyboardButton("💎 Только VIP", callback_data="broadcast_vip")],
            [InlineKeyboardButton("🆕 Только новым", callback_data="broadcast_new")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("💬 РАССЫЛКА СООБЩЕНИЙ\n\nВыберите кому отправить:", reply_markup=reply_markup)
    
    elif query.data.startswith("broadcast_"):
        context.user_data['broadcast_type'] = query.data.replace("broadcast_", "")
        await query.message.edit_text("✍️ Введите текст сообщения для рассылки:\n\n(Отправьте текст следующим сообщением)\n\nДля отмены используйте /cancel")
        return BROADCAST_MESSAGE
    
    elif query.data == "create_promo":
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="admin_promo")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("✍️ Введите код промокода (латиницей):\n\nНапример: SALE20\n\nДля отмены используйте /cancel или нажмите кнопку ниже:", reply_markup=reply_markup)
        return PROMO_CODE
    
    elif query.data == "list_promos":
        await show_promo_list(query, context)
    
    elif query.data.startswith("delete_promo_"):
        promo_code = query.data.replace("delete_promo_", "")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM promo_codes WHERE code=?", (promo_code,))
        conn.commit()
        conn.close()
        await query.answer("✅ Промокод удалён!")
        await show_promo_list(query, context)
    
    elif query.data.startswith("use_promo_"):
        vip_key = query.data.replace("use_promo_", "")
        context.user_data['promo_vip'] = vip_key
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"select_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("🎁 Введите промокод:", reply_markup=reply_markup)
        # Ждём следующее сообщение с промокодом
    
    elif query.data == "admin_search_user":
        context.user_data['searching_user'] = True
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="admin_users_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("🔍 Введите для поиска:\n\n- User ID (число)\n- Username (без @)\n- Имя пользователя\n\nДля отмены используйте /cancel или нажмите кнопку ниже:", reply_markup=reply_markup)
        return SEARCH_USER
    
    elif query.data == "admin_bans":
        await show_bans_menu(query, context)
    
    elif query.data.startswith("ban_user_"):
        user_id = int(query.data.replace("ban_user_", ""))
        logger.info(f"Admin banning user {user_id}")
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO banned_users VALUES (?, ?, ?)",
                  (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Забанен администратором"))
        conn.commit()
        
        # Проверяем что бан сохранился
        c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
        check_ban = c.fetchone()
        logger.info(f"Ban check after insert: {check_ban}")
        
        # Получаем инфо о пользователе для обновления
        c.execute("SELECT * FROM user_activity WHERE user_id=?", (user_id,))
        user_info = c.fetchone()
        conn.close()
        
        if user_info:
            user_id_val, username, full_name, first_start, last_activity = user_info
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            purchases = c.fetchall()
            c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
            ban_info = c.fetchone()
            conn.close()
            
            result_text = f"👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ\n\n"
            result_text += f"ID: {user_id}\n"
            result_text += f"Имя: {full_name}\n"
            result_text += f"Username: @{username}\n"
            result_text += f"Первый визит: {first_start}\n"
            result_text += f"Последняя активность: {last_activity}\n\n"
            result_text += f"🚫 СТАТУС: ЗАБАНЕН\n"
            result_text += f"Дата бана: {ban_info[1]}\n"
            result_text += f"Причина: {ban_info[2]}\n\n"
            
            if purchases:
                result_text += f"💎 Покупки:\n"
                for purchase in purchases:
                    vip_data = VIP_CONFIGS.get(purchase[1])
                    result_text += f"  • {vip_data['emoji']} {vip_data['name']} - {purchase[4]}\n"
            else:
                result_text += "💎 Покупок нет\n"
            
            # Проверяем в режиме ли поиска
            if context.user_data.get('searching_user'):
                result_text += "\n💡 Для поиска следующего пользователя - просто напишите ID или username"
                keyboard = [
                    [InlineKeyboardButton("✅ Разбанить", callback_data=f"unban_user_{user_id}")],
                    [InlineKeyboardButton("❌ Закончить поиск", callback_data="admin_users_menu")]
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton("✅ Разбанить", callback_data=f"unban_user_{user_id}")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="admin_users_menu")]
                ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(result_text, reply_markup=reply_markup)
        else:
            await query.answer("✅ Пользователь забанен!")
            await show_bans_menu(query, context)
    
    elif query.data.startswith("unban_user_"):
        user_id = int(query.data.replace("unban_user_", ""))
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
        conn.commit()
        
        # Получаем инфо о пользователе для обновления
        c.execute("SELECT * FROM user_activity WHERE user_id=?", (user_id,))
        user_info = c.fetchone()
        conn.close()
        
        if user_info:
            user_id_val, username, full_name, first_start, last_activity = user_info
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            purchases = c.fetchall()
            conn.close()
            
            result_text = f"👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ\n\n"
            result_text += f"ID: {user_id}\n"
            result_text += f"Имя: {full_name}\n"
            result_text += f"Username: @{username}\n"
            result_text += f"Первый визит: {first_start}\n"
            result_text += f"Последняя активность: {last_activity}\n\n"
            result_text += f"✅ СТАТУС: АКТИВЕН\n\n"
            
            if purchases:
                result_text += f"💎 Покупки:\n"
                for purchase in purchases:
                    vip_data = VIP_CONFIGS.get(purchase[1])
                    result_text += f"  • {vip_data['emoji']} {vip_data['name']} - {purchase[4]}\n"
            else:
                result_text += "💎 Покупок нет\n"
            
            # Проверяем в режиме ли поиска
            if context.user_data.get('searching_user'):
                result_text += "\n💡 Для поиска следующего пользователя - просто напишите ID или username"
                keyboard = [
                    [InlineKeyboardButton("🚫 Забанить", callback_data=f"ban_user_{user_id}")],
                    [InlineKeyboardButton("❌ Закончить поиск", callback_data="admin_users_menu")]
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton("🚫 Забанить", callback_data=f"ban_user_{user_id}")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="admin_users_menu")]
                ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(result_text, reply_markup=reply_markup)
        else:
            await query.answer("✅ Пользователь разбанен!")
            await show_bans_menu(query, context)
    
    elif query.data == "change_card":
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="admin_settings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("💳 Введите новый номер карты:\n\nДля отмены используйте /cancel или нажмите кнопку ниже:", reply_markup=reply_markup)
        context.user_data['changing_card'] = True
    
    elif query.data == "manage_vips":
        await show_vip_management(query, context)
    
    elif query.data.startswith("toggle_vip_"):
        vip_key = query.data.replace("toggle_vip_", "")
        VIP_CONFIGS[vip_key]['enabled'] = not VIP_CONFIGS[vip_key].get('enabled', True)
        save_vip_config()
        await query.answer(f"✅ VIP {'включен' if VIP_CONFIGS[vip_key]['enabled'] else 'выключен'}!")
        await show_vip_management(query, context)
    
    elif query.data == "admin_editor":
        keyboard = [
            [InlineKeyboardButton("📝 Редактировать тексты", callback_data="editor_texts")],
            [InlineKeyboardButton("💎 Редактировать VIP", callback_data="editor_vips")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("✏️ РЕДАКТОР БОТА\n\nВыберите что хотите отредактировать:", reply_markup=reply_markup)
    
    elif query.data == "editor_texts":
        keyboard = [
            [InlineKeyboardButton("👋 Приветствие", callback_data="edit_text_welcome_user")],
            [InlineKeyboardButton("💳 Инструкция оплаты", callback_data="edit_text_payment_instruction")],
            [InlineKeyboardButton("✅ Сообщение после покупки", callback_data="edit_text_payment_success")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="edit_text_info_text")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="edit_text_support_message")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_editor")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("📝 РЕДАКТИРОВАНИЕ ТЕКСТОВ\n\nВыберите текст для редактирования:", reply_markup=reply_markup)
    
    elif query.data == "editor_vips":
        keyboard = []
        for vip_key, vip_data in VIP_CONFIGS.items():
            keyboard.append([InlineKeyboardButton(
                f"{vip_data['emoji']} {vip_data['name']}", 
                callback_data=f"edit_vip_{vip_key}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_editor")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("💎 РЕДАКТИРОВАНИЕ VIP\n\nВыберите VIP уровень для редактирования:", reply_markup=reply_markup)
    
    elif query.data.startswith("edit_text_"):
        text_key = query.data.replace("edit_text_", "")
        context.user_data['editing_text'] = text_key
        
        text_names = {
            'welcome_user': '👋 Приветствие',
            'payment_instruction': '💳 Инструкция оплаты',
            'payment_success': '✅ Сообщение после покупки',
            'info_text': 'ℹ️ Информация',
            'support_message': '📞 Поддержка'
        }
        
        current_text = get_text(text_key)
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="editor_texts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Редактирование: {text_names.get(text_key, text_key)}\n\n"
            f"📄 Текущий текст:\n{current_text}\n\n"
            f"✍️ Отправьте новый текст следующим сообщением.\n\n"
            f"💡 Доступные переменные:\n"
            f"{{name}} - имя пользователя\n"
            f"{{price}} - цена VIP\n"
            f"{{card}} - номер карты\n"
            f"{{vip_emoji}} - эмодзи VIP\n"
            f"{{vip_name}} - название VIP\n"
            f"{{link}} - ссылка на канал",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("edit_vip_name_"):
        vip_key = query.data.replace("edit_vip_name_", "")
        context.user_data['editing_vip_field'] = {'key': vip_key, 'field': 'name'}
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Введите новое название для VIP:\n\n"
            f"Текущее: {VIP_CONFIGS[vip_key]['name']}",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("edit_vip_desc_"):
        vip_key = query.data.replace("edit_vip_desc_", "")
        context.user_data['editing_vip_field'] = {'key': vip_key, 'field': 'description'}
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Введите новое описание для VIP:\n\n"
            f"Текущее: {VIP_CONFIGS[vip_key]['description']}",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("edit_vip_price_"):
        vip_key = query.data.replace("edit_vip_price_", "")
        context.user_data['editing_vip_field'] = {'key': vip_key, 'field': 'price'}
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Введите новую цену (только число):\n\n"
            f"Текущая: {VIP_CONFIGS[vip_key]['price_num']} ₸",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("edit_vip_emoji_"):
        vip_key = query.data.replace("edit_vip_emoji_", "")
        context.user_data['editing_vip_field'] = {'key': vip_key, 'field': 'emoji'}
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Введите новый эмодзи:\n\n"
            f"Текущий: {VIP_CONFIGS[vip_key]['emoji']}",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("edit_vip_channel_"):
        vip_key = query.data.replace("edit_vip_channel_", "")
        context.user_data['editing_vip_field'] = {'key': vip_key, 'field': 'channel_id'}
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Введите новый ID канала:\n\n"
            f"Текущий: {VIP_CONFIGS[vip_key]['channel_id']}",
            reply_markup=reply_markup
        )
    
    
    elif query.data.startswith("edit_vip_preview_"):
        vip_key = query.data.replace("edit_vip_preview_", "")
        context.user_data['editing_vip_field'] = {'key': vip_key, 'field': 'preview_description'}
        
        current_preview = VIP_CONFIGS[vip_key].get('preview_description', VIP_CONFIGS[vip_key]['description'])
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Введите новое описание предпросмотра:\n\n"
            f"📄 Текущее:\n{current_preview}\n\n"
            f"💡 Это расширенное описание будет показано в предпросмотре.",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("edit_vip_screenshots_"):
        vip_key = query.data.replace("edit_vip_screenshots_", "")
        vip_data = VIP_CONFIGS.get(vip_key)
        
        screenshots = vip_data.get('preview_images', [])
        screenshots_count = len(screenshots)
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить скриншот", callback_data=f"add_screenshot_{vip_key}")],
        ]
        
        if screenshots_count > 0:
            keyboard.append([InlineKeyboardButton("👁 Просмотреть", callback_data=f"view_screenshots_{vip_key}")])
            keyboard.append([InlineKeyboardButton("🗑 Удалить все", callback_data=f"delete_all_screenshots_{vip_key}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"edit_vip_{vip_key}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        screen_text = f"📸 УПРАВЛЕНИЕ СКРИНШОТАМИ\n{vip_data['emoji']} {vip_data['name']}\n\n"
        screen_text += f"📊 Добавлено скриншотов: {screenshots_count}\n\n"
        
        if screenshots_count > 0:
            screen_text += "✅ Скриншоты сохранены и будут показаны в предпросмотре"
        else:
            screen_text += "💡 Нажмите 'Добавить скриншот' и отправьте фото"
        
        await query.message.edit_text(screen_text, reply_markup=reply_markup)
    
    elif query.data.startswith("add_screenshot_"):
        vip_key = query.data.replace("add_screenshot_", "")
        context.user_data['adding_screenshot'] = vip_key
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_screenshots_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"📸 ДОБАВЛЕНИЕ СКРИНШОТА\n\n"
            f"📤 Отправьте фото боту\n\n"
            f"💡 Можно отправить несколько фото подряд\n"
            f"✅ Каждое фото будет автоматически сохранено",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("view_screenshots_"):
        vip_key = query.data.replace("view_screenshots_", "")
        vip_data = VIP_CONFIGS.get(vip_key)
        screenshots = vip_data.get('preview_images', [])
        
        await query.message.delete()
        
        if screenshots:
            for i, file_id in enumerate(screenshots, 1):
                try:
                    await context.bot.send_photo(
                        chat_id=user.id,
                        photo=file_id,
                        caption=f"📸 Скриншот {i}/{len(screenshots)}"
                    )
                except Exception as e:
                    logger.error(f"Error sending screenshot: {e}")
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_vip_screenshots_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user.id,
            text=f"📸 Показано: {len(screenshots)}",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("delete_all_screenshots_"):
        vip_key = query.data.replace("delete_all_screenshots_", "")
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_screenshots_{vip_key}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"edit_vip_screenshots_{vip_key}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            "⚠️ ПОДТВЕРЖДЕНИЕ\n\n"
            "Удалить ВСЕ скриншоты?",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("confirm_delete_screenshots_"):
        vip_key = query.data.replace("confirm_delete_screenshots_", "")
        VIP_CONFIGS[vip_key]['preview_images'] = []
        save_vip_config()
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_vip_screenshots_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            "✅ Все скриншоты удалены!",
            reply_markup=reply_markup
        )

    # Этот блок теперь срабатывает ТОЛЬКО для точного "edit_vip_{vip_key}" без суффиксов
    elif query.data.startswith("edit_vip_") and not any(query.data.startswith(f"edit_vip_{suffix}_") for suffix in ['name', 'desc', 'price', 'emoji', 'channel', 'preview', 'screenshots']):
        vip_key = query.data.replace("edit_vip_", "")
        vip_data = VIP_CONFIGS[vip_key]
        
        keyboard = [
            [InlineKeyboardButton("✏️ Название", callback_data=f"edit_vip_name_{vip_key}")],
            [InlineKeyboardButton("📋 Описание", callback_data=f"edit_vip_desc_{vip_key}")],
            [InlineKeyboardButton("👁 Предпросмотр", callback_data=f"edit_vip_preview_{vip_key}")],
            [InlineKeyboardButton("📸 Скриншоты", callback_data=f"edit_vip_screenshots_{vip_key}")],
            [InlineKeyboardButton("💰 Цена", callback_data=f"edit_vip_price_{vip_key}")],
            [InlineKeyboardButton("🎨 Эмодзи", callback_data=f"edit_vip_emoji_{vip_key}")],
            [InlineKeyboardButton("🔗 ID канала", callback_data=f"edit_vip_channel_{vip_key}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="editor_vips")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"💎 Редактирование {vip_data['emoji']} {vip_data['name']}\n\n"
            f"📋 Описание: {vip_data['description']}\n"
            f"💰 Цена: {vip_data['price']}\n"
            f"🔗 ID канала: {vip_data['channel_id']}\n"
            f"📸 Скриншотов: {len(vip_data.get('preview_images', []))}\n\n"
            f"Выберите что изменить:",
            reply_markup=reply_markup
        )
    
    elif query.data == "admin_promo":
        await show_promo_menu(query, context)
    
    elif query.data == "admin_editor":
        keyboard = [
            [InlineKeyboardButton("📝 Редактировать тексты", callback_data="editor_texts")],
            [InlineKeyboardButton("💎 Редактировать VIP", callback_data="editor_vips")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("✏️ РЕДАКТОР БОТА\n\nВыберите что хотите отредактировать:", reply_markup=reply_markup)
    
    elif query.data == "editor_texts":
        keyboard = [
            [InlineKeyboardButton("👋 Приветствие", callback_data="edit_text_welcome_message")],
            [InlineKeyboardButton("💳 Инструкция оплаты", callback_data="edit_text_payment_instruction")],
            [InlineKeyboardButton("✅ Успешная покупка", callback_data="edit_text_purchase_success")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="edit_text_info_message")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="edit_text_support_message")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_editor")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("📝 РЕДАКТИРОВАНИЕ ТЕКСТОВ\n\nВыберите текст для редактирования:", reply_markup=reply_markup)
    
    elif query.data == "editor_vips":
        keyboard = []
        for vip_key, vip_data in VIP_CONFIGS.items():
            keyboard.append([InlineKeyboardButton(
                f"{vip_data['emoji']} {vip_data['name']}", 
                callback_data=f"edit_vip_{vip_key}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_editor")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("💎 РЕДАКТИРОВАНИЕ VIP\n\nВыберите VIP уровень:", reply_markup=reply_markup)
    
    elif query.data.startswith("edit_text_"):
        text_key = query.data.replace("edit_text_", "")
        context.user_data['editing_text'] = text_key
        
        text_names = {
            'welcome_message': 'Приветствие',
            'payment_instruction': 'Инструкция по оплате',
            'purchase_success': 'Успешная покупка',
            'info_message': 'Информация',
            'support_message': 'Поддержка'
        }
        
        current_text = get_bot_text(text_key) or "Не установлено"
        
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="editor_texts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"✏️ Редактирование: {text_names.get(text_key, text_key)}\n\n"
            f"📄 Текущий текст:\n{current_text}\n\n"
            f"✍️ Отправьте новый текст:\n\n"
            f"Доступные переменные:\n"
            f"{{name}} - имя пользователя\n"
            f"{{price}} - цена VIP\n"
            f"{{card}} - номер карты\n"
            f"{{vip_emoji}} - эмодзи VIP\n"
            f"{{vip_name}} - название VIP\n"
            f"{{link}} - ссылка на канал",
            reply_markup=reply_markup
        )
    
    elif query.data == "admin_settings":
        await show_settings(query, context)
    
    elif query.data == "admin_export":
        keyboard = [
            [InlineKeyboardButton("📊 Excel - Все пользователи", callback_data="export_users_excel")],
            [InlineKeyboardButton("📊 Excel - Продажи", callback_data="export_sales_excel")],
            [InlineKeyboardButton("💾 Backup БД", callback_data="export_db")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("💾 ЭКСПОРТ ДАННЫХ\n\nВыберите формат:", reply_markup=reply_markup)
    
    elif query.data.startswith("export_"):
        await handle_export(query, context)
    
    elif query.data.startswith("approve_"):
        await handle_approve(query, context)
    
    elif query.data.startswith("reject_"):
        await handle_reject(query, context)

# ========== ПОКУПКА VIP ==========

async def handle_buy(query, context, user):
    vip_key = query.data.replace("buy_", "")
    vip_data = VIP_CONFIGS.get(vip_key)
    
    if not vip_data:
        await query.message.edit_text("❌ Ошибка. Вернитесь в меню /start")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=? AND vip_type=?", (user.id, vip_key))
        existing = c.fetchone()
        conn.close()
        
        if existing:
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                f"✅ Вы уже купили доступ к {vip_data['emoji']} {vip_data['name']}!\n\nВаша персональная ссылка:\n{existing[5]}",
                reply_markup=reply_markup
            )
            return
        
        # Сохраняем в ожидающие
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO pending_payments VALUES (?, ?, ?, ?, ?)",
                  (user.id, vip_key, user.username or "Нет username", 
                   user.first_name or "Пользователь", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        
        log_action(user.id, "buy_request", f"VIP: {vip_key}")
        
        card_number = get_setting('card_number') or CARD_NUMBER
        
        payment_text_template = get_bot_text('payment_instruction')
        if payment_text_template:
            payment_text = f"{vip_data['emoji']} {vip_data['name']}\n\n"
            payment_text += payment_text_template.replace('{price}', vip_data['price']).replace('{card}', card_number)
        else:
            payment_text = f"{vip_data['emoji']} {vip_data['name']}\n\n"
            payment_text += f"💳 Инструкция по оплате:\n\n"
            payment_text += f"1️⃣ Переведите {vip_data['price']} на карту:\n{card_number}\n\n"
            payment_text += f"2️⃣ Сделайте скриншот или чек оплаты\n\n"
            payment_text += f"3️⃣ Отправьте чек боту:\n   📸 Скриншот (фото)\n   📄 PDF файл\n   📎 Любой документ\n\n"
            payment_text += f"⏳ После проверки платежа (обычно 1-5 минут) вы получите персональную ссылку на канал!\n\n"
            payment_text += f"📝 Важно: отправьте подтверждение оплаты в любом формате!"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(payment_text, reply_markup=reply_markup)
        logger.info(f"Payment instructions sent to user {user.id} for {vip_key}")
        
    except Exception as e:
        logger.error(f"Error in buy button: {type(e).__name__}: {e}")
        await query.message.reply_text(f"❌ Произошла ошибка. Попробуйте /start")

# ========== ОБРАБОТКА ЧЕКОВ ==========

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Проверка бана
    if is_banned(user.id):
        await update.message.reply_text("❌ Вы заблокированы и не можете использовать бот.")
        return
    
    # Проверяем добавление скриншотов
    if 'adding_screenshot' in context.user_data and user.id == ADMIN_ID:
        if update.message.photo:
            vip_key = context.user_data['adding_screenshot']
            file_id = update.message.photo[-1].file_id
            
            # Добавляем file_id
            if 'preview_images' not in VIP_CONFIGS[vip_key]:
                VIP_CONFIGS[vip_key]['preview_images'] = []
            
            VIP_CONFIGS[vip_key]['preview_images'].append(file_id)
            save_vip_config()
            
            screenshots_count = len(VIP_CONFIGS[vip_key]['preview_images'])
            
            keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"edit_vip_screenshots_{vip_key}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Скриншот добавлен!\n\n"
                f"📊 Всего: {screenshots_count}\n\n"
                f"📤 Можете отправить ещё или нажмите 'Отмена'",
                reply_markup=reply_markup
            )
            return
        else:
            await update.message.reply_text("❌ Отправьте именно фото")
            return
    
    if update.message.photo:
        file_to_send = update.message.photo[-1].file_id
        file_type = "фото"
    elif update.message.document:
        file_to_send = update.message.document.file_id
        file_type = "документ"
    else:
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM pending_payments WHERE user_id=?", (user.id,))
    pending = c.fetchall()
    conn.close()
    
    if not pending:
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ Сначала выберите VIP уровень и нажмите 'Купить доступ'!\n\nИспользуйте команду /start",
            reply_markup=reply_markup
        )
        return
    
    if len(pending) > 1:
        keyboard = []
        for pend in pending:
            vip_key = pend[1]
            vip_data = VIP_CONFIGS.get(vip_key)
            keyboard.append([InlineKeyboardButton(
                f"{vip_data['emoji']} {vip_data['name']} - {vip_data['price']}", 
                callback_data=f"send_check_{vip_key}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['pending_file'] = file_to_send
        context.user_data['pending_file_type'] = file_type
        
        await update.message.reply_text(
            "💳 У вас несколько ожидающих покупок.\n\nВыберите, за какой VIP уровень этот чек:",
            reply_markup=reply_markup
        )
        return
    
    vip_key = pending[0][1]
    await send_check_to_admin(update, context, user, vip_key, file_to_send, file_type)

async def send_check_to_admin(update, context, user, vip_key, file_to_send, file_type):
    vip_data = VIP_CONFIGS.get(vip_key)
    
    if not vip_data:
        if update.message:
            await update.message.reply_text("❌ Ошибка. Попробуйте /start")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_{user.id}_{vip_key}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}_{vip_key}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption_text = f"🔔 Новая оплата на проверку!\n\n"
    caption_text += f"{vip_data['emoji']} {vip_data['name']} - {vip_data['price']}\n\n"
    caption_text += f"👤 {user.first_name}\n"
    caption_text += f"🆔 ID: {user.id}\n"
    caption_text += f"📱 @{user.username if user.username else 'Нет'}\n"
    caption_text += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    caption_text += f"📎 Тип: {file_type}"
    
    try:
        if file_type == "фото":
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_to_send, caption=caption_text, reply_markup=reply_markup)
        else:
            await context.bot.send_document(chat_id=ADMIN_ID, document=file_to_send, caption=caption_text, reply_markup=reply_markup)
        
        success_text = f"✅ Ваш чек за {vip_data['emoji']} {vip_data['name']} отправлен на проверку!\n\n⏳ Обычно проверка занимает 1-5 минут.\nМы уведомим вас, как только доступ будет активирован!"
        
        if update.message:
            await update.message.reply_text(success_text)
        elif update.callback_query:
            await update.callback_query.message.reply_text(success_text)
            
    except Exception as e:
        logger.error(f"Error sending to admin: {e}")
        error_text = "⚠️ Ошибка отправки. Попробуйте позже."
        if update.message:
            await update.message.reply_text(error_text)

async def handle_approve(query, context):
    parts = query.data.split("_")
    user_id = int(parts[1])
    vip_key = parts[2]
    vip_data = VIP_CONFIGS.get(vip_key)
    
    if not vip_data:
        await query.message.edit_text("❌ Ошибка: неизвестный VIP уровень")
        return
    
    try:
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=vip_data['channel_id'],
            member_limit=1,
            name=f"User_{user_id}_{vip_key}"
        )
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM pending_payments WHERE user_id=? AND vip_type=?", (user_id, vip_key))
        user_data = c.fetchone()
        
        if user_data:
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user_id, vip_key, user_data[2], user_data[3], 
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                       invite_link.invite_link, "active"))
            c.execute("DELETE FROM pending_payments WHERE user_id=? AND vip_type=?", (user_id, vip_key))
            conn.commit()
        conn.close()
        
        log_action(user_id, "purchase_approved", f"VIP: {vip_key}")
        
        user_keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back")]]
        user_reply_markup = InlineKeyboardMarkup(user_keyboard)
        
        success_text_template = get_bot_text('purchase_success')
        if success_text_template:
            success_text = success_text_template.replace('{vip_emoji}', vip_data['emoji'])
            success_text = success_text.replace('{vip_name}', vip_data['name'])
            success_text = success_text.replace('{link}', invite_link.invite_link)
        else:
            success_text = f"✅ Оплата подтверждена!\n\n{vip_data['emoji']} {vip_data['name']}\n\n🎉 Ваша персональная ссылка на канал:\n{invite_link.invite_link}\n\n⚠️ Важно:\n- Ссылка работает только для вас\n- Не передавайте её другим\n- Доступ навсегда\n\nПриятного просмотра! 🔥"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=success_text,
            reply_markup=user_reply_markup
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Назад в админ-панель", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query.message.photo or query.message.document:
            await query.message.edit_caption(
                caption=f"✅ Оплата подтверждена\nПользователь: {user_id}\nVIP: {vip_data['emoji']} {vip_data['name']}\n\nСсылка: {invite_link.invite_link}",
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text(
                f"✅ Оплата подтверждена\nПользователь: {user_id}\nVIP: {vip_data['emoji']} {vip_data['name']}\n\nСсылка: {invite_link.invite_link}",
                reply_markup=reply_markup
            )
        
    except Exception as e:
        logger.error(f"Error approving payment: {e}")
        await query.message.edit_text(f"❌ Ошибка: {str(e)}")

async def handle_reject(query, context):
    parts = query.data.split("_")
    user_id = int(parts[1])
    vip_key = parts[2]
    vip_data = VIP_CONFIGS.get(vip_key)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pending_payments WHERE user_id=? AND vip_type=?", (user_id, vip_key))
    conn.commit()
    conn.close()
    
    log_action(user_id, "purchase_rejected", f"VIP: {vip_key}")
    
    user_keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back")]]
    user_reply_markup = InlineKeyboardMarkup(user_keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=f"❌ Ваша оплата за {vip_data['emoji']} {vip_data['name']} не прошла проверку.\n\nПожалуйста, проверьте правильность перевода и попробуйте снова.",
        reply_markup=user_reply_markup
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад в админ-панель", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query.message.photo or query.message.document:
        await query.message.edit_caption(
            caption=f"❌ Оплата отклонена\nПользователь: {user_id}\nVIP: {vip_data['emoji']} {vip_data['name']}",
            reply_markup=reply_markup
        )
    else:
        await query.message.edit_text(
            f"❌ Оплата отклонена\nПользователь: {user_id}\nVIP: {vip_data['emoji']} {vip_data['name']}",
            reply_markup=reply_markup
        )

# ========== АДМИН СТАТИСТИКА ==========

async def show_admin_stats(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM users")
    total_buyers = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users")
    total_purchases = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM pending_payments")
    pending = c.fetchone()[0]
    
    # Статистика по VIP
    vip_stats = {}
    total_revenue = 0
    for vip_key, vip_data in VIP_CONFIGS.items():
        c.execute("SELECT COUNT(*) FROM users WHERE vip_type=?", (vip_key,))
        count = c.fetchone()[0]
        vip_stats[vip_key] = count
        total_revenue += count * vip_data['price_num']
    
    # Продажи за сегодня
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM users WHERE payment_date LIKE ?", (f"{today}%",))
    today_sales = c.fetchone()[0]
    
    # Продажи за неделю
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM users WHERE payment_date >= ?", (week_ago,))
    week_sales = c.fetchone()[0]
    
    # Конверсия
    c.execute("SELECT COUNT(*) FROM user_activity")
    total_users = c.fetchone()[0]
    conversion = (total_buyers / total_users * 100) if total_users > 0 else 0
    
    c.execute("SELECT * FROM users ORDER BY payment_date DESC LIMIT 5")
    recent = c.fetchall()
    conn.close()
    
    stats_text = "📊 СТАТИСТИКА БОТА\n\n"
    stats_text += f"💰 Общий доход: {total_revenue} ₸\n"
    stats_text += f"👥 Уникальных покупателей: {total_buyers}\n"
    stats_text += f"💎 Всего покупок: {total_purchases}\n"
    stats_text += f"⏳ Ожидают проверки: {pending}\n"
    stats_text += f"📈 Конверсия: {conversion:.1f}%\n\n"
    
    stats_text += f"📅 Продажи за сегодня: {today_sales}\n"
    stats_text += f"📆 Продажи за неделю: {week_sales}\n\n"
    
    stats_text += "📈 По VIP уровням:\n"
    for vip_key, count in vip_stats.items():
        vip_data = VIP_CONFIGS[vip_key]
        revenue = count * vip_data['price_num']
        stats_text += f"{vip_data['emoji']} {vip_data['name']}: {count} ({revenue} ₸)\n"
    
    if recent:
        stats_text += f"\n🕒 Последние покупки:\n"
        for user_data in recent:
            vip_data = VIP_CONFIGS.get(user_data[1], {"emoji": "💎", "name": user_data[1]})
            stats_text += f"{vip_data['emoji']} {user_data[3]} - {user_data[4]}\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(stats_text, reply_markup=reply_markup)

async def show_all_users(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Получаем всех пользователей, кто нажал /start
    c.execute("SELECT COUNT(*) FROM user_activity")
    total_users = c.fetchone()[0]
    
    # Получаем последних 50 пользователей
    c.execute("SELECT * FROM user_activity ORDER BY last_activity DESC LIMIT 50")
    users = c.fetchall()
    
    # Считаем VIP пользователей
    c.execute("SELECT COUNT(DISTINCT user_id) FROM users")
    vip_count = c.fetchone()[0]
    
    conn.close()
    
    if not users:
        users_text = "👥 Пользователей пока нет"
    else:
        users_text = f"👥 ВСЕ ПОЛЬЗОВАТЕЛИ БОТА\n\n"
        users_text += f"📊 Всего запустило бот: {total_users}\n"
        users_text += f"💎 Из них VIP: {vip_count}\n"
        users_text += f"👤 Обычных: {total_users - vip_count}\n\n"
        users_text += f"📋 Последние 50 пользователей:\n\n"
        
        for user_data in users:
            user_id, username, full_name, first_start, last_activity = user_data
            username_str = f"@{username}" if username != "Нет username" else "Нет"
            
            # Проверяем есть ли VIP
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users WHERE user_id=?", (user_id,))
            is_vip = c.fetchone()[0] > 0
            
            # Проверяем забанен ли
            c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
            is_banned = c.fetchone() is not None
            conn.close()
            
            status = "💎" if is_vip else "👤"
            status += " 🚫" if is_banned else ""
            
            users_text += f"{status} {full_name}\n"
            users_text += f"   {username_str} | ID: {user_id}\n"
            users_text += f"   Последний визит: {last_activity}\n\n"
        
        if total_users > 50:
            users_text += f"... и ещё {total_users - 50} пользователей"
    
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск пользователя", callback_data="admin_search_user")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_users_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(users_text, reply_markup=reply_markup)

async def show_activity(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM user_activity")
    total_users = c.fetchone()[0]
    
    now = datetime.now()
    day_ago = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT COUNT(*) FROM user_activity WHERE last_activity >= ?", (day_ago,))
    active_24h = c.fetchone()[0]
    
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT COUNT(*) FROM user_activity WHERE last_activity >= ?", (week_ago,))
    active_week = c.fetchone()[0]
    
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT COUNT(*) FROM user_activity WHERE last_activity >= ?", (month_ago,))
    active_month = c.fetchone()[0]
    
    c.execute("SELECT * FROM user_activity ORDER BY last_activity DESC LIMIT 10")
    recent_active = c.fetchall()
    
    conn.close()
    
    activity_text = "📈 АКТИВНОСТЬ ПОЛЬЗОВАТЕЛЕЙ\n\n"
    activity_text += f"👥 Всего заходило в бот: {total_users}\n\n"
    activity_text += f"🕐 За последние 24 часа: {active_24h}\n"
    activity_text += f"📅 За последнюю неделю: {active_week}\n"
    activity_text += f"📆 За последний месяц: {active_month}\n\n"
    
    if recent_active:
        activity_text += "🕒 Последние активные:\n\n"
        for user_data in recent_active[:5]:
            username = f"@{user_data[1]}" if user_data[1] != "Нет username" else "Нет"
            activity_text += f"• {user_data[2]}\n  {username} | ID: {user_data[0]}\n  {user_data[4]}\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(activity_text, reply_markup=reply_markup)

async def show_pending(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM pending_payments ORDER BY request_date DESC")
    pending = c.fetchall()
    conn.close()
    
    if not pending:
        pending_text = "✅ Нет ожидающих проверки"
    else:
        pending_text = "⏳ Ожидают проверки:\n\n"
        for user_data in pending:
            username = f"@{user_data[2]}" if user_data[2] != "Нет username" else "Нет"
            vip_data = VIP_CONFIGS.get(user_data[1], {"emoji": "💎", "name": user_data[1]})
            pending_text += f"{vip_data['emoji']} {user_data[3]}\n  {username} | ID: {user_data[0]}\n  VIP: {vip_data['name']}\n  Дата: {user_data[4]}\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(pending_text, reply_markup=reply_markup)

# ========== ПРОМОКОДЫ ==========

async def show_promo_menu(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM promo_codes")
    total_codes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM promo_usage")
    total_used = c.fetchone()[0]
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать промокод", callback_data="create_promo")],
        [InlineKeyboardButton("📋 Список промокодов", callback_data="list_promos")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    promo_text = f"🎁 ПРОМОКОДЫ\n\n"
    promo_text += f"📊 Всего промокодов: {total_codes}\n"
    promo_text += f"✅ Использовано: {total_used}\n\n"
    promo_text += f"Выберите действие:"
    
    await query.message.edit_text(promo_text, reply_markup=reply_markup)

# ========== НАСТРОЙКИ ==========

async def show_settings(query, context):
    card_number = get_setting('card_number') or CARD_NUMBER
    
    keyboard = [
        [InlineKeyboardButton("💳 Изменить номер карты", callback_data="change_card")],
        [InlineKeyboardButton("🔧 VIP уровни", callback_data="manage_vips")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    settings_text = f"⚙️ НАСТРОЙКИ БОТА\n\n"
    settings_text += f"💳 Номер карты: {card_number}\n\n"
    settings_text += f"Выберите что хотите изменить:"
    
    await query.message.edit_text(settings_text, reply_markup=reply_markup)

# ========== ЭКСПОРТ ДАННЫХ ==========

async def handle_export(query, context):
    export_type = query.data.replace("export_", "")
    
    try:
        if export_type == "users_excel":
            await export_users_excel(query, context)
        elif export_type == "sales_excel":
            await export_sales_excel(query, context)
        elif export_type == "db":
            await export_database(query, context)
    except Exception as e:
        logger.error(f"Export error: {e}")
        await query.message.edit_text(f"❌ Ошибка экспорта: {str(e)}")

async def export_users_excel(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY payment_date DESC")
    users = c.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['User ID', 'VIP Type', 'Username', 'Full Name', 'Payment Date', 'Invite Link', 'Status'])
    
    for user in users:
        writer.writerow(user)
    
    output.seek(0)
    file_bytes = BytesIO(output.getvalue().encode('utf-8'))
    file_bytes.name = f"users_{datetime.now().strftime('%Y%m%d')}.csv"
    
    await context.bot.send_document(
        chat_id=ADMIN_ID,
        document=file_bytes,
        caption="📊 Экспорт пользователей"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_export")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("✅ Файл отправлен!", reply_markup=reply_markup)

async def export_sales_excel(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, vip_type, full_name, payment_date FROM users ORDER BY payment_date DESC")
    sales = c.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['User ID', 'VIP', 'Name', 'Date', 'Amount'])
    
    for sale in sales:
        vip_data = VIP_CONFIGS.get(sale[1])
        writer.writerow([sale[0], vip_data['name'], sale[2], sale[3], vip_data['price']])
    
    output.seek(0)
    file_bytes = BytesIO(output.getvalue().encode('utf-8'))
    file_bytes.name = f"sales_{datetime.now().strftime('%Y%m%d')}.csv"
    
    await context.bot.send_document(
        chat_id=ADMIN_ID,
        document=file_bytes,
        caption="📊 Экспорт продаж"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_export")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("✅ Файл отправлен!", reply_markup=reply_markup)

async def export_database(query, context):
    try:
        with open(DB_PATH, 'rb') as db_file:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=db_file,
                caption=f"💾 Backup БД - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_export")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("✅ Backup отправлен!", reply_markup=reply_markup)
    except Exception as e:
        await query.message.edit_text(f"❌ Ошибка: {str(e)}")

# ========== ПРОМОКОДЫ - ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ==========

async def show_promo_list(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes ORDER BY created_date DESC")
    promos = c.fetchall()
    conn.close()
    
    if not promos:
        promo_text = "📋 Промокодов пока нет"
        keyboard = [
            [InlineKeyboardButton("➕ Создать промокод", callback_data="create_promo")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_promo")]
        ]
    else:
        promo_text = "📋 СПИСОК ПРОМОКОДОВ:\n\n"
        keyboard = []
        
        for promo in promos:
            code, discount, uses_left, created, valid_until = promo
            promo_text += f"🎁 {code}\n"
            promo_text += f"   Скидка: {discount}%\n"
            promo_text += f"   Осталось: {uses_left} исп.\n"
            promo_text += f"   Создан: {created}\n\n"
            
            keyboard.append([InlineKeyboardButton(f"🗑 Удалить {code}", callback_data=f"delete_promo_{code}")])
        
        keyboard.append([InlineKeyboardButton("➕ Создать новый", callback_data="create_promo")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_promo")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(promo_text, reply_markup=reply_markup)

# ========== УПРАВЛЕНИЕ БАНАМИ ==========

async def show_bans_menu(query, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM banned_users ORDER BY ban_date DESC")
    banned = c.fetchall()
    conn.close()
    
    if not banned:
        ban_text = "✅ Забаненных пользователей нет"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_users_menu")]]
    else:
        ban_text = "🚫 ЗАБАНЕННЫЕ ПОЛЬЗОВАТЕЛИ:\n\n"
        keyboard = []
        
        for ban in banned:
            user_id, ban_date, reason = ban
            
            # Получаем инфо о пользователе
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT * FROM user_activity WHERE user_id=?", (user_id,))
            user_info = c.fetchone()
            conn.close()
            
            if user_info:
                ban_text += f"👤 {user_info[2]} (@{user_info[1]})\n"
                ban_text += f"   ID: {user_id}\n"
                ban_text += f"   Дата бана: {ban_date}\n"
                ban_text += f"   Причина: {reason}\n\n"
            else:
                ban_text += f"👤 ID: {user_id}\n"
                ban_text += f"   Дата бана: {ban_date}\n\n"
            
            keyboard.append([InlineKeyboardButton(f"✅ Разбанить {user_id}", callback_data=f"unban_user_{user_id}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_users_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(ban_text, reply_markup=reply_markup)

# ========== УПРАВЛЕНИЕ VIP УРОВНЯМИ ==========

async def show_vip_management(query, context):
    vip_text = "🔧 УПРАВЛЕНИЕ VIP УРОВНЯМИ:\n\n"
    keyboard = []
    
    for vip_key, vip_data in VIP_CONFIGS.items():
        status = "✅" if vip_data.get('enabled', True) else "❌"
        vip_text += f"{status} {vip_data['emoji']} {vip_data['name']} - {vip_data['price']}\n"
        
        button_text = f"{'❌ Выключить' if vip_data.get('enabled', True) else '✅ Включить'} {vip_data['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"toggle_vip_{vip_key}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_settings")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(vip_text, reply_markup=reply_markup)

# ========== ОБРАБОТЧИКИ ТЕКСТОВЫХ СООБЩЕНИЙ ==========

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    # Проверка бана (но не для админа и не для команды /cancel)
    if text != "/cancel" and user.id != ADMIN_ID and is_banned(user.id):
        await update.message.reply_text("❌ Вы заблокированы и не можете использовать бот.")
        return ConversationHandler.END
    
    # Отмена действия
    if text == "/cancel":
        context.user_data.clear()
        await update.message.reply_text("❌ Действие отменено")
        await start(update, context)
        return ConversationHandler.END
    
    # Редактирование текста бота
    if 'editing_text' in context.user_data:
        text_key = context.user_data['editing_text']
        set_bot_text(text_key, text.strip())
        context.user_data.pop('editing_text')
        
        keyboard = [[InlineKeyboardButton("◀️ К текстам", callback_data="editor_texts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ Текст сохранён!", reply_markup=reply_markup)
        return
    
    # Обработка промокода от пользователя
    if 'promo_vip' in context.user_data:
        vip_key = context.user_data['promo_vip']
        promo_code = text.strip().upper()
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Проверяем промокод
        c.execute("SELECT * FROM promo_codes WHERE code=?", (promo_code,))
        promo = c.fetchone()
        
        keyboard_back = [[InlineKeyboardButton("◀️ Назад", callback_data=f"select_{vip_key}")]]
        reply_markup_back = InlineKeyboardMarkup(keyboard_back)
        
        if not promo:
            await update.message.reply_text("❌ Промокод не найден!", reply_markup=reply_markup_back)
            conn.close()
            context.user_data.pop('promo_vip')
            return
        
        code, discount, uses_left, created, valid_until = promo
        
        if uses_left <= 0:
            await update.message.reply_text("❌ Промокод исчерпан!", reply_markup=reply_markup_back)
            conn.close()
            context.user_data.pop('promo_vip')
            return
        
        # Проверяем использовал ли уже
        c.execute("SELECT * FROM promo_usage WHERE user_id=? AND code=?", (user.id, promo_code))
        if c.fetchone():
            await update.message.reply_text("❌ Вы уже использовали этот промокод!", reply_markup=reply_markup_back)
            conn.close()
            context.user_data.pop('promo_vip')
            return
        
        conn.close()
        
        vip_data = VIP_CONFIGS[vip_key]
        new_price = int(vip_data['price_num'] * (100 - discount) / 100)
        
        keyboard = [
            [InlineKeyboardButton("💳 Купить со скидкой", callback_data=f"buy_{vip_key}")],
            [InlineKeyboardButton("◀️ Назад", callback_data=f"select_{vip_key}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Промокод применён!\n\n"
            f"{vip_data['emoji']} {vip_data['name']}\n"
            f"💰 Старая цена: {vip_data['price']}\n"
            f"🎁 Скидка: {discount}%\n"
            f"💵 Новая цена: {new_price} ₸\n\n"
            f"Нажмите кнопку для покупки:",
            reply_markup=reply_markup
        )
        
        context.user_data.pop('promo_vip')
        return
    
    # Смена номера карты
    if context.user_data.get('changing_card'):
        set_setting('card_number', text.strip())
        context.user_data.pop('changing_card')
        
        keyboard = [[InlineKeyboardButton("◀️ К настройкам", callback_data="admin_settings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"✅ Номер карты изменён на: {text.strip()}", reply_markup=reply_markup)
        return
    
    # Редактирование текста бота
    if 'editing_text' in context.user_data:
        text_key = context.user_data['editing_text']
        new_text = text.strip()
        set_text(text_key, new_text)
        context.user_data.pop('editing_text')
        
        # Проверяем что текст действительно сохранился
        saved_text = get_bot_text(text_key)
        
        keyboard = [[InlineKeyboardButton("◀️ К текстам", callback_data="editor_texts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if saved_text == new_text:
            await update.message.reply_text(
                f"✅ Текст успешно сохранён!\n\n"
                f"📄 Сохранённый текст:\n{saved_text[:200]}{'...' if len(saved_text) > 200 else ''}", 
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"⚠️ Текст сохранён, но возможны проблемы.\n\n"
                f"Отправлено: {new_text[:100]}...\n"
                f"Сохранено: {saved_text[:100] if saved_text else 'NULL'}...", 
                reply_markup=reply_markup
            )
        return
    
    # Редактирование VIP
    if 'editing_vip_field' in context.user_data:
        vip_info = context.user_data['editing_vip_field']
        vip_key = vip_info['key']
        field = vip_info['field']
        
        if field == 'price':
            try:
                price_num = int(text.strip())
                VIP_CONFIGS[vip_key]['price_num'] = price_num
                VIP_CONFIGS[vip_key]['price'] = f"{price_num} ₸"
            except ValueError:
                await update.message.reply_text("❌ Ошибка! Введите число.")
                return
        elif field == 'channel_id':
            try:
                channel_id = int(text.strip())
                VIP_CONFIGS[vip_key]['channel_id'] = channel_id
            except ValueError:
                await update.message.reply_text("❌ Ошибка! Введите число (например: -1001234567890).")
                return
        elif field == 'name':
            VIP_CONFIGS[vip_key]['name'] = text.strip()
        elif field == 'description':
            VIP_CONFIGS[vip_key]['description'] = text.strip()
        elif field == 'preview_description':
            VIP_CONFIGS[vip_key]['preview_description'] = text.strip()
        elif field == 'emoji':
            VIP_CONFIGS[vip_key]['emoji'] = text.strip()
        
        save_vip_config()
        context.user_data.pop('editing_vip_field')
        
        keyboard = [[InlineKeyboardButton("◀️ К VIP", callback_data=f"edit_vip_{vip_key}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"✅ VIP обновлён!", reply_markup=reply_markup)
        return
    
    # Рассылка
    if 'broadcast_type' in context.user_data:
        await handle_broadcast(update, context, text)
        return BROADCAST_MESSAGE
    
    # Создание промокода - шаг 1: код
    if context.user_data.get('creating_promo_step') == 'code':
        promo_code = text.strip().upper()
        
        if not promo_code.replace('_', '').isalnum():
            await update.message.reply_text("❌ Промокод должен содержать только буквы и цифры!")
            return PROMO_CODE
        
        context.user_data['promo_code'] = promo_code
        context.user_data['creating_promo_step'] = 'discount'
        await update.message.reply_text("✍️ Введите размер скидки (число от 1 до 99):\n\nНапример: 20")
        return PROMO_DISCOUNT
    
    # Создание промокода - шаг 2: скидка
    if context.user_data.get('creating_promo_step') == 'discount':
        try:
            discount = int(text.strip())
            if discount < 1 or discount > 99:
                await update.message.reply_text("❌ Скидка должна быть от 1 до 99%!")
                return PROMO_DISCOUNT
            
            context.user_data['promo_discount'] = discount
            context.user_data['creating_promo_step'] = 'uses'
            await update.message.reply_text("✍️ Введите количество использований:\n\nНапример: 10\n(0 = безлимит)")
            return PROMO_DISCOUNT
        except ValueError:
            await update.message.reply_text("❌ Введите число!")
            return PROMO_DISCOUNT
    
    # Создание промокода - шаг 3: количество
    if context.user_data.get('creating_promo_step') == 'uses':
        try:
            uses = int(text.strip())
            if uses < 0:
                await update.message.reply_text("❌ Количество не может быть отрицательным!")
                return PROMO_DISCOUNT
            
            promo_code = context.user_data['promo_code']
            discount = context.user_data['promo_discount']
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO promo_codes VALUES (?, ?, ?, ?, ?)",
                      (promo_code, discount, uses if uses > 0 else 999999, 
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S"), None))
            conn.commit()
            conn.close()
            
            keyboard = [[InlineKeyboardButton("◀️ К промокодам", callback_data="admin_promo")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Промокод создан!\n\n"
                f"🎁 Код: {promo_code}\n"
                f"💰 Скидка: {discount}%\n"
                f"📊 Использований: {uses if uses > 0 else '∞'}",
                reply_markup=reply_markup
            )
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("❌ Введите число!")
            return PROMO_DISCOUNT
    
    # Поиск пользователя
    if context.user_data.get('searching_user'):
        await handle_user_search(update, context, text)
        # НЕ завершаем - остаемся в режиме поиска
        return SEARCH_USER

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text):
    broadcast_type = context.user_data.get('broadcast_type', 'all')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if broadcast_type == 'all':
        c.execute("SELECT DISTINCT user_id FROM user_activity")
    elif broadcast_type == 'vip':
        c.execute("SELECT DISTINCT user_id FROM users")
    elif broadcast_type == 'new':
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT user_id FROM user_activity WHERE first_start >= ?", (week_ago,))
    
    users = c.fetchall()
    conn.close()
    
    sent_count = 0
    failed_count = 0
    
    status_msg = await update.message.reply_text(f"📤 Начинаю рассылку для {len(users)} пользователей...")
    
    for user in users:
        user_id = user[0]
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sent_count += 1
        except Exception as e:
            logger.error(f"Broadcast error for user {user_id}: {e}")
            failed_count += 1
    
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {sent_count}\n"
        f"❌ Ошибок: {failed_count}"
    )
    
    # Добавляем кнопку назад
    keyboard = [[InlineKeyboardButton("◀️ В админ-панель", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text="📊 Рассылка завершена! Что дальше?",
        reply_markup=reply_markup
    )
    
    log_action(ADMIN_ID, "broadcast", f"Type: {broadcast_type}, Sent: {sent_count}")
    context.user_data.clear()

async def handle_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Поиск по ID
    if query_text.isdigit():
        c.execute("SELECT * FROM user_activity WHERE user_id=?", (int(query_text),))
        user = c.fetchone()
        
        if user:
            user_id, username, full_name, first_start, last_activity = user
            
            # Получаем покупки
            c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            purchases = c.fetchall()
            
            # Проверяем бан
            c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
            ban_info = c.fetchone()
            
            result_text = f"👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ\n\n"
            result_text += f"ID: {user_id}\n"
            result_text += f"Имя: {full_name}\n"
            result_text += f"Username: @{username}\n"
            result_text += f"Первый визит: {first_start}\n"
            result_text += f"Последняя активность: {last_activity}\n\n"
            
            if ban_info:
                result_text += f"🚫 СТАТУС: ЗАБАНЕН\n"
                result_text += f"Дата бана: {ban_info[1]}\n"
                result_text += f"Причина: {ban_info[2]}\n\n"
            
            if purchases:
                result_text += f"💎 Покупки:\n"
                for purchase in purchases:
                    vip_data = VIP_CONFIGS.get(purchase[1])
                    result_text += f"  • {vip_data['emoji']} {vip_data['name']} - {purchase[4]}\n"
            else:
                result_text += "💎 Покупок нет\n"
            
            keyboard = []
            if ban_info:
                keyboard.append([InlineKeyboardButton("✅ Разбанить", callback_data=f"unban_user_{user_id}")])
            else:
                keyboard.append([InlineKeyboardButton("🚫 Забанить", callback_data=f"ban_user_{user_id}")])
            
            keyboard.append([InlineKeyboardButton("❌ Закончить поиск", callback_data="admin_users_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            result_text += "\n💡 Для поиска следующего пользователя - просто напишите ID или username"
            
            await update.message.reply_text(result_text, reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("❌ Закончить поиск", callback_data="admin_users_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("❌ Пользователь не найден!\n\n💡 Попробуйте ещё раз или нажмите кнопку ниже", reply_markup=reply_markup)
    
    # Поиск по username или имени
    else:
        # Убираем @ если пользователь его ввел
        search_query = query_text.lstrip('@').strip()
        
        logger.info(f"Searching for username/name: '{search_query}'")
        
        c.execute("SELECT * FROM user_activity WHERE username LIKE ? OR full_name LIKE ?", 
                  (f"%{search_query}%", f"%{search_query}%"))
        users = c.fetchall()
        
        logger.info(f"Found {len(users)} users: {[(u[0], u[1]) for u in users]}")
        
        if users:
            # Если найден ОДИН пользователь - показываем детальную информацию
            if len(users) == 1:
                user_id, username, full_name, first_start, last_activity = users[0]
                
                logger.info(f"Single user found: ID={user_id}, username={username}, name={full_name}")
                
                # Получаем покупки
                c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
                purchases = c.fetchall()
                
                # Проверяем бан
                c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
                ban_info = c.fetchone()
                
                result_text = f"👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ\n\n"
                result_text += f"ID: {user_id}\n"
                result_text += f"Имя: {full_name}\n"
                result_text += f"Username: @{username}\n"
                result_text += f"Первый визит: {first_start}\n"
                result_text += f"Последняя активность: {last_activity}\n\n"
                
                if ban_info:
                    result_text += f"🚫 СТАТУС: ЗАБАНЕН\n"
                    result_text += f"Дата бана: {ban_info[1]}\n"
                    result_text += f"Причина: {ban_info[2]}\n\n"
                
                if purchases:
                    result_text += f"💎 Покупки:\n"
                    for purchase in purchases:
                        vip_data = VIP_CONFIGS.get(purchase[1])
                        result_text += f"  • {vip_data['emoji']} {vip_data['name']} - {purchase[4]}\n"
                else:
                    result_text += "💎 Покупок нет\n"
                
                keyboard = []
                if ban_info:
                    keyboard.append([InlineKeyboardButton("✅ Разбанить", callback_data=f"unban_user_{user_id}")])
                else:
                    keyboard.append([InlineKeyboardButton("🚫 Забанить", callback_data=f"ban_user_{user_id}")])
                
                keyboard.append([InlineKeyboardButton("❌ Закончить поиск", callback_data="admin_users_menu")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                result_text += "\n💡 Для поиска следующего пользователя - просто напишите ID или username"
                
                await update.message.reply_text(result_text, reply_markup=reply_markup)
            
            # Если найдено несколько - показываем список
            else:
                result_text = f"🔍 Найдено пользователей: {len(users)}\n\n"
                result_text += f"💡 Для действий (бан/разбан) введите точный ID пользователя\n\n"
                
                for user in users[:20]:
                    user_id, username, full_name, first_start, last_activity = user
                    
                    # Проверяем бан
                    c.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
                    is_banned = c.fetchone() is not None
                    
                    # Проверяем VIP
                    c.execute("SELECT COUNT(*) FROM users WHERE user_id=?", (user_id,))
                    is_vip = c.fetchone()[0] > 0
                    
                    status = "💎" if is_vip else "👤"
                    status += " 🚫" if is_banned else ""
                    
                    result_text += f"{status} {full_name}\n"
                    result_text += f"   @{username} | ID: {user_id}\n"
                    result_text += f"   Последний визит: {last_activity}\n\n"
                
                if len(users) > 20:
                    result_text += f"\n📋 Показано первых 20 из {len(users)}\n"
                
                keyboard = [
                    [InlineKeyboardButton("❌ Закончить поиск", callback_data="admin_users_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(result_text, reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("❌ Закончить поиск", callback_data="admin_users_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"❌ Ничего не найдено по запросу: {query_text}\n\n💡 Попробуйте ещё раз или нажмите кнопку ниже", reply_markup=reply_markup)
    
    conn.close()
    # НЕ очищаем context.user_data, чтобы остаться в режиме поиска
    # context.user_data.clear()

# Обработчик для начала создания промокода
async def start_promo_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['creating_promo_step'] = 'code'
    return PROMO_CODE

# Обработчик для начала поиска
async def start_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['searching_user'] = True
    return SEARCH_USER

# Отмена действия
async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("🏠 В главное меню", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("❌ Действие отменено", reply_markup=reply_markup)
    return ConversationHandler.END

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========

def main():
    init_db()
    load_vip_config()  # Загружаем VIP из БД если есть
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler для рассылки
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^broadcast_")],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)]
    )
    
    # ConversationHandler для создания промокода
    promo_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^create_promo$")],
        states={
            PROMO_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)],
            PROMO_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)]
    )
    
    # ConversationHandler для поиска пользователя
    search_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^admin_search_user$")],
        states={
            SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)]
    )
    
    # Основные обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(broadcast_handler)
    application.add_handler(promo_handler)
    application.add_handler(search_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, payment_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    logger.info("🚀 Бот запущен с ПОЛНЫМ функционалом!")
    logger.info("✅ Статистика и аналитика")
    logger.info("✅ Рассылки")
    logger.info("✅ Промокоды")
    logger.info("✅ Управление пользователями")
    logger.info("✅ Экспорт данных")
    logger.info("✅ Отзывы")
    logger.info("✅ Банов система")
    logger.info("✅ Настройки бота")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
