import logging
import json
import os
import re
import sqlite3
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import math

# Настройки
BOT_TOKEN = "8368020354:AAH2fOMICkzWAI6d8y1lUL8xN-rvfRrrykE"
CREATOR_CHAT_ID = 7759987050
SPECIAL_USER_ID = 7759987050
DATA_FILE = "users_data.json"

# 🔥 НОВЫЕ НАСТРОЙКИ
PRICE_PER_MINUTE = 0.65  # 0.5$ за минуту

# 🔥 ДОБАВЛЯЕМ ГЛОБАЛЬНЫЙ ТОП (не сбрасывается при очистке статистики)
TOP_EARNERS_DATA_FILE = "top_earners.json"

# Включим логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# JSON Database functions
def init_json_db():
    """Инициализация JSON базы данных"""
    try:
        if not os.path.exists(DATA_FILE):
            default_data = {
                "users": {},
                "rentals": {},
                "pending_messages": {},
                "settings": {
                    "last_rental_id": 0,
                    "last_message_id": 0
                }
            }
            save_json_data(default_data)
            logger.info("✅ JSON database initialized successfully")
        else:
            # Проверяем что все необходимые ключи существуют
            data = load_json_data()
            needs_save = False

            if "settings" not in data:
                data["settings"] = {
                    "last_rental_id": 0,
                    "last_message_id": 0
                }
                needs_save = True

            if "rentals" not in data:
                data["rentals"] = {}
                needs_save = True

            if "pending_messages" not in data:
                data["pending_messages"] = {}
                needs_save = True

            if needs_save:
                save_json_data(data)
                logger.info("✅ JSON database structure updated")

        # 🔥 Инициализируем файл для топа зарабатывающих
        init_top_earners_db()

    except Exception as e:
        logger.error(f"❌ JSON database initialization error: {e}")


def init_top_earners_db():
    """Инициализация базы данных для топа зарабатывающих"""
    try:
        if not os.path.exists(TOP_EARNERS_DATA_FILE):
            default_data = {
                "all_time_top": [],
                "last_updated": datetime.now().isoformat()
            }
            with open(TOP_EARNERS_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
            logger.info("✅ Top earners database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Top earners database initialization error: {e}")


def update_top_earners():
    """Обновление топа зарабатывающих"""
    try:
        users = get_all_users_with_earnings()

        top_data = {
            "all_time_top": users[:20],  # Топ-20 за все время
            "last_updated": datetime.now().isoformat()
        }

        with open(TOP_EARNERS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(top_data, f, ensure_ascii=False, indent=2)

        logger.info("✅ Top earners updated successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating top earners: {e}")
        return False


def get_top_earners():
    """Получить топ зарабатывающих"""
    try:
        if os.path.exists(TOP_EARNERS_DATA_FILE):
            with open(TOP_EARNERS_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("all_time_top", [])
        return []
    except Exception as e:
        logger.error(f"❌ Error getting top earners: {e}")
        return []


async def handle_admin_panel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)


def load_json_data():
    """Загрузка данных из JSON"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Проверяем и добавляем отсутствующие ключи
            if "users" not in data:
                data["users"] = {}
            if "rentals" not in data:
                data["rentals"] = {}
            if "pending_messages" not in data:
                data["pending_messages"] = {}
            if "settings" not in data:
                data["settings"] = {"last_rental_id": 0, "last_message_id": 0}

            return data

        # Если файла нет, возвращаем структуру по умолчанию
        return {
            "users": {},
            "rentals": {},
            "pending_messages": {},
            "settings": {
                "last_rental_id": 0,
                "last_message_id": 0
            }
        }
    except Exception as e:
        logger.error(f"❌ Error loading JSON data: {e}")
        return {
            "users": {},
            "rentals": {},
            "pending_messages": {},
            "settings": {
                "last_rental_id": 0,
                "last_message_id": 0
            }
        }


def save_json_data(data):
    """Сохранение данных в JSON"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"❌ Error saving JSON data: {e}")
        return False


def ensure_admin_user():
    """Создает администратора если его нет в базе"""
    try:
        data = load_json_data()
        admin_id_str = str(CREATOR_CHAT_ID)

        if admin_id_str not in data["users"]:
            data["users"][admin_id_str] = {
                "username": "admin_bot",
                "referrer_id": None,
                "balance": 0.0,
                "total_earnings": 0.0,
                "referral_earnings": 0.0,
                "registered_date": datetime.now().isoformat(),
                "has_access": True
            }
            if save_json_data(data):
                logger.info(f"✅ Admin user {CREATOR_CHAT_ID} created successfully")
            else:
                logger.error(f"❌ Failed to create admin user {CREATOR_CHAT_ID}")
        else:
            # Убедимся что администратор имеет доступ
            if not data["users"][admin_id_str].get("has_access"):
                data["users"][admin_id_str]["has_access"] = True
                save_json_data(data)
                logger.info(f"✅ Admin user {CREATOR_CHAT_ID} access enabled")
            else:
                logger.info(f"✅ Admin user {CREATOR_CHAT_ID} already exists with access")

    except Exception as e:
        logger.error(f"❌ Error ensuring admin user: {e}")


def get_user(user_id):
    """Получить пользователя по ID"""
    data = load_json_data()
    user_str = str(user_id)
    user_data = data["users"].get(user_str)

    if user_data:
        logger.info(f"✅ User {user_id} found: {user_data}")
    else:
        logger.info(f"❌ User {user_id} not found in database")

    return user_data


def add_user(user_id, username, referrer_id=None, has_access=False):
    """Добавить пользователя"""
    data = load_json_data()
    user_str = str(user_id)

    # Всегда обновляем данные пользователя
    data["users"][user_str] = {
        "username": username,
        "referrer_id": referrer_id,
        "balance": 0.0,
        "total_earnings": 0.0,
        "referral_earnings": 0.0,
        "registered_date": datetime.now().isoformat(),
        "has_access": has_access
    }

    success = save_json_data(data)
    if success:
        logger.info(f"✅ User {user_id} added/updated with access: {has_access}, referrer: {referrer_id}")
    else:
        logger.error(f"❌ Failed to save user {user_id}")

    return success


def update_user_earnings(user_id, earnings, referral_earnings=0):
    """Обновить заработок пользователя"""
    try:
        data = load_json_data()
        user_str = str(user_id)

        if user_str in data["users"]:
            if "total_earnings" not in data["users"][user_str]:
                data["users"][user_str]["total_earnings"] = 0.0
            if "referral_earnings" not in data["users"][user_str]:
                data["users"][user_str]["referral_earnings"] = 0.0

            data["users"][user_str]["total_earnings"] = round(data["users"][user_str]["total_earnings"] + earnings, 2)
            data["users"][user_str]["referral_earnings"] = round(
                data["users"][user_str]["referral_earnings"] + referral_earnings, 2)

            if save_json_data(data):
                logger.info(f"✅ User {user_id} earnings updated: +{earnings}$, referral: +{referral_earnings}$")

                # 🔥 ОБНОВЛЯЕМ ТОП ПРИ ИЗМЕНЕНИИ ЗАРАБОТКА
                update_top_earners()

                return True

        return False
    except Exception as e:
        logger.error(f"❌ Error updating user earnings {user_id}: {e}")
        return False


def reset_all_earnings():
    """Сбросить весь заработок у всех пользователей"""
    try:
        data = load_json_data()

        for user_id, user_data in data["users"].items():
            user_data["total_earnings"] = 0.0
            user_data["referral_earnings"] = 0.0
            user_data["balance"] = 0.0

        if save_json_data(data):
            logger.info("✅ All user earnings reset to zero")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error resetting all earnings: {e}")
        return False


def reset_today_earnings():
    """Сбросить заработок за сегодня"""
    try:
        data = load_json_data()
        today = date.today().isoformat()
        reset_count = 0

        # Сбрасываем заработки у пользователей
        for user_id, user_data in data["users"].items():
            # Проверяем дату регистрации или последнего обновления
            user_date = user_data.get("last_earnings_update", user_data.get("registered_date", ""))
            if user_date.startswith(today):
                user_data["total_earnings"] = 0.0
                user_data["referral_earnings"] = 0.0
                user_data["balance"] = 0.0
                reset_count += 1

        # Сбрасываем аренды за сегодня
        today_rentals = []
        for rental_id, rental_data in data["rentals"].items():
            rental_date = rental_data.get("rental_date", "")
            if rental_date.startswith(today):
                today_rentals.append(rental_id)

        for rental_id in today_rentals:
            del data["rentals"][rental_id]

        if save_json_data(data):
            logger.info(f"✅ Today's earnings reset: {reset_count} users, {len(today_rentals)} rentals")
            return True, reset_count, len(today_rentals)
        return False, 0, 0

    except Exception as e:
        logger.error(f"❌ Error resetting today's earnings: {e}")
        return False, 0, 0


def add_rental(renter_id, phone_number, duration_minutes=None, earnings=None, referrer_id=None, message_id=None,
               actual_minutes=None):
    """Добавить аренду"""
    try:
        data = load_json_data()

        # Проверяем что settings существует
        if "settings" not in data:
            data["settings"] = {"last_rental_id": 0, "last_message_id": 0}

        # Получаем следующий ID аренды
        rental_id = data["settings"]["last_rental_id"] + 1

        # Создаем данные аренды
        rental_data = {
            "renter_id": renter_id,
            "phone_number": phone_number,
            "rental_date": datetime.now().isoformat(),
            "status": "active"
        }

        # Добавляем опциональные поля
        if duration_minutes is not None:
            rental_data["duration_minutes"] = float(duration_minutes)
        if earnings is not None:
            rental_data["earnings"] = float(earnings)
        if referrer_id is not None:
            rental_data["referrer_id"] = referrer_id
        if message_id is not None:
            rental_data["message_id"] = message_id
        if actual_minutes is not None:
            rental_data["actual_minutes"] = float(actual_minutes)

        # Сохраняем аренду
        data["rentals"][str(rental_id)] = rental_data
        data["settings"]["last_rental_id"] = rental_id

        if save_json_data(data):
            logger.info(f"✅ Rental added: ID {rental_id}, User {renter_id}, Phone {phone_number}")
            return rental_id
        else:
            logger.error("❌ Failed to save rental data")
            return None

    except Exception as e:
        logger.error(f"❌ Error adding rental for user {renter_id}: {e}")
        return None


def update_rental_earnings(rental_id, actual_minutes, earnings):
    """Обновить аренду с фактическими данными"""
    try:
        data = load_json_data()
        rental_str = str(rental_id)

        if rental_str in data["rentals"]:
            data["rentals"][rental_str]["actual_minutes"] = float(actual_minutes)
            data["rentals"][rental_str]["earnings"] = float(earnings)
            data["rentals"][rental_str]["status"] = "completed"
            data["rentals"][rental_str]["completed_date"] = datetime.now().isoformat()

            if save_json_data(data):
                logger.info(f"✅ Rental {rental_id} updated successfully: {actual_minutes}min, ${earnings}")
                return True
            else:
                logger.error(f"❌ Failed to save rental {rental_id} data")
                return False
        else:
            logger.error(f"❌ Rental {rental_id} not found in database")
            return False

    except Exception as e:
        logger.error(f"❌ Error updating rental {rental_id}: {e}")
        return False


def add_pending_message(rental_id, user_id, message_text, message_type="text"):
    """Добавить ожидающее сообщение"""
    try:
        data = load_json_data()

        # Проверяем что settings существует
        if "settings" not in data:
            data["settings"] = {"last_rental_id": 0, "last_message_id": 0}

        message_id = data["settings"]["last_message_id"] + 1

        data["pending_messages"][str(message_id)] = {
            "rental_id": rental_id,
            "user_id": user_id,
            "message_text": message_text,
            "message_type": message_type,
            "status": "pending",
            "created_date": datetime.now().isoformat()
        }

        data["settings"]["last_message_id"] = message_id

        if save_json_data(data):
            return message_id
        return None
    except Exception as e:
        logger.error(f"❌ Error adding pending message: {e}")
        return None


def get_rental_by_message_id(message_id):
    """Найти аренду по ID сообщения"""
    data = load_json_data()
    for rental_id, rental in data["rentals"].items():
        if rental.get("message_id") == message_id:
            return (
                int(rental_id),  # id
                rental["renter_id"],  # renter_id
                rental["phone_number"],  # phone_number
                rental.get("duration_minutes"),  # duration_minutes
                rental.get("earnings"),  # earnings
                rental.get("referrer_id"),  # referrer_id
                rental["rental_date"],  # rental_date
                rental["status"],  # status
                rental.get("message_id"),  # message_id
                rental.get("actual_minutes")  # actual_minutes
            )
    return None


def get_user_rentals(user_id):
    """Получить аренды пользователя"""
    data = load_json_data()
    user_rentals = []

    for rental_id, rental in data["rentals"].items():
        if rental["renter_id"] == user_id:
            user_rentals.append((
                int(rental_id),  # id
                rental["renter_id"],  # renter_id
                rental["phone_number"],  # phone_number
                rental.get("duration_minutes"),  # duration_minutes
                rental.get("earnings"),  # earnings
                rental.get("referrer_id"),  # referrer_id
                rental["rental_date"],  # rental_date
                rental["status"],  # status
                rental.get("message_id"),  # message_id
                rental.get("actual_minutes")  # actual_minutes
            ))

    # Сортируем по дате (новые сначала)
    user_rentals.sort(key=lambda x: x[6], reverse=True)
    return user_rentals


def get_referrer_stats(user_id):
    """Получить статистику реферера"""
    try:
        data = load_json_data()
        referral_count = 0
        total_commission = 0.0
        referral_rentals = []

        # Считаем рефералов и их аренды
        for uid, user_data in data.get("users", {}).items():
            if user_data.get("referrer_id") == user_id:
                referral_count += 1

                # Находим аренды этого реферала
                referral_id = int(uid)
                for rental_id, rental in data.get("rentals", {}).items():
                    if rental.get("renter_id") == referral_id and rental.get("actual_minutes"):
                        minutes = rental.get("actual_minutes", 0)
                        earnings = rental.get("earnings", 0)
                        commission = earnings * 0.1
                        total_commission += commission

                        referral_rentals.append({
                            "user_id": referral_id,
                            "username": user_data.get("username", f"user_{referral_id}"),
                            "phone": rental.get("phone_number"),
                            "minutes": minutes,
                            "earnings": earnings,
                            "commission": commission,
                            "date": rental.get("completed_date", rental.get("rental_date"))
                        })

        # Сортируем по дате (новые сначала)
        referral_rentals.sort(key=lambda x: x["date"], reverse=True)

        return (referral_count, total_commission, referral_rentals)

    except Exception as e:
        logger.error(f"❌ Error in get_referrer_stats for user {user_id}: {e}")
        return (0, 0.0, [])


def get_all_users_with_earnings():
    """Получить всех пользователей с заработком"""
    try:
        data = load_json_data()
        users_with_earnings = []

        for user_id, user_data in data.get("users", {}).items():
            total_earnings = user_data.get("total_earnings", 0)
            referral_earnings = user_data.get("referral_earnings", 0)
            overall_earnings = total_earnings + referral_earnings

            if overall_earnings > 0:
                users_with_earnings.append({
                    "user_id": int(user_id),
                    "username": user_data.get("username", f"user_{user_id}"),
                    "total_earnings": total_earnings,
                    "referral_earnings": referral_earnings,
                    "overall_earnings": overall_earnings
                })

        # Сортируем по общему заработку (убывание)
        users_with_earnings.sort(key=lambda x: x["overall_earnings"], reverse=True)
        return users_with_earnings

    except Exception as e:
        logger.error(f"❌ Error getting users with earnings: {e}")
        return []


def get_detailed_stats():
    """Получить детальную статистику"""
    try:
        data = load_json_data()

        total_users = len(data.get("users", {}))
        total_rentals = len(data.get("rentals", {}))
        completed_rentals = len([r for r in data.get("rentals", {}).values() if r.get("status") == "completed"])

        total_earnings = 0
        total_minutes = 0

        for rental in data.get("rentals", {}).values():
            if rental.get("status") == "completed":
                total_earnings += rental.get("earnings", 0)
                total_minutes += rental.get("actual_minutes", 0)

        users_with_earnings = get_all_users_with_earnings()

        return {
            "total_users": total_users,
            "total_rentals": total_rentals,
            "completed_rentals": completed_rentals,
            "total_earnings": round(total_earnings, 2),
            "total_minutes": round(total_minutes, 2),
            "users_with_earnings": users_with_earnings,
            "top_earners": users_with_earnings[:5] if users_with_earnings else []
        }

    except Exception as e:
        logger.error(f"❌ Error getting detailed stats: {e}")
        return {
            "total_users": 0,
            "total_rentals": 0,
            "completed_rentals": 0,
            "total_earnings": 0,
            "total_minutes": 0,
            "users_with_earnings": [],
            "top_earners": []
        }


# Валидация российских и казахстанских номеров
def validate_phone_number(phone):
    try:
        cleaned_phone = re.sub(r'[^\d+]', '', phone)

        # Российские номера
        russian_patterns = [
            r'^\+7\d{10}$',  # +79123456789
            r'^8\d{10}$',  # 89123456789
            r'^7\d{10}$',  # 79123456789
        ]

        # Казахстанские номера
        kazakh_patterns = [
            r'^\+77\d{9}$',  # +77123456789
            r'^87\d{9}$',  # 87123456789
            r'^77\d{9}$',  # 77123456789
        ]

        for pattern in russian_patterns + kazakh_patterns:
            if re.match(pattern, cleaned_phone):
                return cleaned_phone

        return None
    except Exception as e:
        logger.error(f"❌ Error validating phone {phone}: {e}")
        return None


# Генерация реферальной ссылки
def generate_referral_link(user_id):
    return f"https://t.me/Whatsapp_Luxury_bot?start={user_id}"


# Проверка доступа пользователя (только по реферальной ссылке)
def has_access(user_id):
    try:
        # Администратор и специальный пользователь всегда имеют доступ
        if user_id in [CREATOR_CHAT_ID, SPECIAL_USER_ID]:
            logger.info(f"✅ User {user_id} has access (admin/special)")
            return True

        user_data = get_user(user_id)
        if user_data and user_data.get("has_access"):
            logger.info(f"✅ User {user_id} has access (registered with referral)")
            return True

        logger.info(f"❌ User {user_id} NO ACCESS - data: {user_data}")
        return False

    except Exception as e:
        logger.error(f"❌ Error checking access for {user_id}: {e}")
        return False


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        logger.info(f"👤 User {user.id} started the bot with args: {context.args}")

        # 🔥 ПРОВЕРКА USERNAME
        if not user.username:
            await update.message.reply_text(
                "⚠️ *Внимание! У вас не установлен username*\n\n"
                "Для работы с ботом необходимо установить username в настройках Telegram.\n\n"
                "*Как установить username:*\n"
                "1. Откройте Настройки Telegram\n"
                "2. Нажмите 'Изменить профиль'\n"
                "3. Установите 'Имя пользователя'\n"
                "4. Сохраните изменения\n\n"
                "❕ *Важно:* Если вы смените username после получения выплат, "
                "возможны проблемы с идентификацией!\n\n"
                "После установки username перезапустите бота: /start",
                parse_mode='Markdown'
            )
            return

        # Проверяем реферальную ссылку
        referral_id = None
        user_has_access = False

        if context.args and len(context.args) > 0 and context.args[0].startswith('ref'):
            try:
                referral_id = int(context.args[0][3:])
                logger.info(f"🔗 Referral link detected: {referral_id} for user {user.id}")

                # Проверяем существует ли реферер
                referrer = get_user(referral_id)
                if referrer:
                    logger.info(f"✅ Referrer {referral_id} found")
                    user_has_access = True

                    # Уведомляем реферера
                    try:
                        referrer_name = referrer.get("username", f"user_{referral_id}")
                        await context.bot.send_message(
                            chat_id=referral_id,
                            text=f"🎉 По вашей ссылке зарегистрировался новый пользователь: @{user.username}"
                        )
                        logger.info(f"✅ Notification sent to referrer {referral_id}")
                    except Exception as e:
                        logger.error(f"❌ Error notifying referrer {referral_id}: {e}")
                else:
                    # Реферер не найден, но все равно даем доступ
                    logger.warning(f"❌ Referrer {referral_id} not found, but granting access anyway")
                    user_has_access = True

            except (ValueError, IndexError) as e:
                logger.error(f"❌ Error processing referral link: {e}")
                user_has_access = True  # Даем доступ даже при ошибке
        else:
            logger.info(f"📛 No referral link for user {user.id}")
            # 🔥 ИЗМЕНЕНИЕ: Даем доступ даже без реферальной ссылки
            user_has_access = True

        # Получаем существующего пользователя для проверки
        existing_user = get_user(user.id)

        # 🔥 ИЗМЕНЕНИЕ: Если пользователь уже был зарегистрирован, сохраняем его доступ
        if existing_user and existing_user.get("has_access"):
            user_has_access = True
            logger.info(f"✅ User {user.id} already has access, preserving it")

        # Регистрируем/обновляем пользователя с правильным доступом
        add_user(user.id, user.username, referral_id, user_has_access)

        # 🔥 ИЗМЕНЕНИЕ: Даем доступ всем кто прошел проверку username
        if not has_access(user.id):
            await update.message.reply_text(
                "❌ *Доступ запрещен!*\n\n"
                "Для использования бота необходимо зарегистрироваться по реферальной ссылке.\n\n"
                "Если у вас нет реферальной ссылки, обратитесь к администратору: @kolprey",
                parse_mode='Markdown'
            )
            return

        # Если доступ есть - показываем меню
        keyboard = [
            [KeyboardButton("📱 Сдать номер в аренду")],
            [KeyboardButton("👥 Реферальная система"), KeyboardButton("📊 Моя статистика")],
            [KeyboardButton("💰 Статистика рефералов"), KeyboardButton("🏆 Топ зарабатывающих")],
            [KeyboardButton("ℹ️ Помощь")]
        ]

        # 🔥 ДОБАВЛЯЕМ АДМИН ПАНЕЛЬ ДЛЯ СОЗДАТЕЛЯ
        if user.id == CREATOR_CHAT_ID:
            keyboard.append([KeyboardButton("👑 Админ панель")])

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        welcome_text = f"Привет, @{user.username}!\n\n"
        welcome_text += "📱 *WhatsApp Аренда Бот*\n\n"
        welcome_text += "Сдавайте свои WhatsApp номера в аренду и зарабатывайте!\n\n"
        welcome_text += f"💰 *Тариф:* {PRICE_PER_MINUTE}$ за минуту\n\n"
        welcome_text += f"💳 *Минимальная выплата:* 3минуты\n\n"
        welcome_text += "👥 Также вы можете приглашать людей и получать за них выплату"

        if referral_id:
            referrer_user = get_user(referral_id)
            referrer_name = referrer_user.get("username",
                                              f"user_{referral_id}") if referrer_user else f"user_{referral_id}"
            welcome_text += f"\n\nВы были приглашены пользователем: @{referrer_name}"

        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
        logger.info(f"✅ User {user.id} successfully started the bot with access")

    except Exception as e:
        logger.error(f"❌ Error in start command for user {user.id}: {e}")
        await update.message.reply_text(
            "❌ *Доступ запрещен!*\n\n"
            "Для использования бота необходимо зарегистрироваться по реферальной ссылке.\n\n"
        )


# 🔥 АДМИН ПАНЕЛЬ - исправленная версия
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        keyboard = [
            [KeyboardButton("📊 Детальная статистика")],
            [KeyboardButton("👥 Пользователи с заработком")],
            [KeyboardButton("🔄 Сбросить все заработки")],
            [KeyboardButton("🗑️ Очистить статистику за сегодня")],
            [KeyboardButton("🔙 Назад в меню")]
        ]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        admin_text = "👑 *Админ панель*\n\n"
        admin_text += "Выберите действие:"

        await update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"❌ Error in admin_panel: {e}")
        await update.message.reply_text("❌ Ошибка в админ панели")


async def handle_admin_detailed_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детальная статистика для админа"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            await update.message.reply_text("❌ У вас нет доступа")
            return

        stats = get_detailed_stats()

        stats_text = "📊 *Детальная статистика*\n\n"
        stats_text += f"👥 Всего пользователей: *{stats['total_users']}*\n"
        stats_text += f"📈 Всего аренд: *{stats['total_rentals']}*\n"
        stats_text += f"✅ Завершено аренд: *{stats['completed_rentals']}*\n"
        stats_text += f"⏱ Всего минут: *{stats['total_minutes']}*\n"
        stats_text += f"💰 Общий оборот: *{stats['total_earnings']}$*\n\n"

        if stats['top_earners']:
            stats_text += "🏆 *Топ-5 зарабатывающих:*\n"
            for i, earner in enumerate(stats['top_earners'], 1):
                username_display = f"@{earner['username']}" if not earner['username'].startswith(
                    'user_') else f"ID: {earner['user_id']}"
                stats_text += f"{i}. {username_display} - *{earner['overall_earnings']}$*\n"
        else:
            stats_text += "📭 Нет пользователей с заработком"

        await update.message.reply_text(stats_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_detailed_stats: {e}")
        await update.message.reply_text("❌ Ошибка при получении статистики")


async def handle_admin_users_with_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список пользователей с заработком"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            await update.message.reply_text("❌ У вас нет доступа")
            return

        users = get_all_users_with_earnings()

        if not users:
            await update.message.reply_text("📭 Нет пользователей с заработком")
            return

        # Разбиваем на части если сообщение слишком длинное
        users_text = "👥 *Пользователи с заработком*\n\n"

        for i, user_data in enumerate(users, 1):
            username_display = f"@{user_data['username']}" if not user_data['username'].startswith(
                'user_') else f"ID: {user_data['user_id']}"
            users_text += f"*{i}. {username_display}*\n"
            users_text += f"   💰 Личный: {user_data['total_earnings']}$\n"
            users_text += f"   👥 Реф: {user_data['referral_earnings']}$\n"
            users_text += f"   🏆 Общий: *{user_data['overall_earnings']}$*\n"
            users_text += "   ━━━━━━━━━━━━━━━━━━━━\n"

            # Если сообщение становится слишком длинным, отправляем часть
            if len(users_text) > 3000:
                await update.message.reply_text(users_text, parse_mode='Markdown')
                users_text = "👥 *Пользователи с заработком (продолжение)*\n\n"

        if users_text:
            await update.message.reply_text(users_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_users_with_earnings: {e}")
        await update.message.reply_text("❌ Ошибка при получении списка пользователей")


async def handle_admin_reset_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс всех заработков"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            await update.message.reply_text("❌ У вас нет доступа")
            return

        # Подтверждение сброса
        keyboard = [
            [KeyboardButton("✅ Да, сбросить все"), KeyboardButton("❌ Нет, отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "⚠️ *ВНИМАНИЕ!*\n\n"
            "Вы собираетесь сбросить ВЕСЬ заработок у всех пользователей.\n"
            "Это действие нельзя отменить!\n\n"
            "Подтвердите сброс:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_reset_earnings: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе заработков")


async def handle_admin_reset_today_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс заработков за сегодня"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            await update.message.reply_text("❌ У вас нет доступа")
            return

        # Подтверждение сброса
        keyboard = [
            [KeyboardButton("✅ Да, очистить сегодня"), KeyboardButton("❌ Нет, отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "⚠️ *ВНИМАНИЕ!*\n\n"
            "Вы собираетесь очистить статистику за СЕГОДНЯ.\n"
            "Это действие нельзя отменить!\n\n"
            "Подтвердите очистку:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_reset_today_earnings: {e}")
        await update.message.reply_text("❌ Ошибка при очистке статистики за сегодня")


async def handle_admin_confirm_reset_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение сброса статистики за сегодня"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            return

        success, users_reset, rentals_reset = reset_today_earnings()

        if success:
            # Возвращаем админ клавиатуру
            keyboard = [
                [KeyboardButton("📊 Детальная статистика")],
                [KeyboardButton("👥 Пользователи с заработком")],
                [KeyboardButton("🔄 Сбросить все заработки")],
                [KeyboardButton("🗑️ Очистить статистику за сегодня")],
                [KeyboardButton("🔙 Назад в меню")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                f"✅ Статистика за сегодня успешно очищена!\n\n"
                f"📊 Результаты:\n"
                f"• Пользователей сброшено: {users_reset}\n"
                f"• Аренд удалено: {rentals_reset}",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Ошибка при очистке статистики за сегодня")

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_confirm_reset_today: {e}")
        await update.message.reply_text("❌ Ошибка при очистке статистики за сегодня")


async def handle_admin_confirm_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение сброса заработков"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            return

        if reset_all_earnings():
            # Возвращаем админ клавиатуру
            keyboard = [
                [KeyboardButton("📊 Детальная статистика")],
                [KeyboardButton("👥 Пользователи с заработком")],
                [KeyboardButton("🔄 Сбросить все заработки")],
                [KeyboardButton("🗑️ Очистить статистику за сегодня")],
                [KeyboardButton("🔙 Назад в меню")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                "✅ Все заработки успешно сброшены до нуля!",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Ошибка при сбросе заработков")

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_confirm_reset: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе заработков")


async def handle_admin_cancel_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена сброса заработков"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            return

        # Возвращаем админ клавиатуру
        keyboard = [
            [KeyboardButton("📊 Детальная статистика")],
            [KeyboardButton("👥 Пользователи с заработком")],
            [KeyboardButton("🔄 Сбросить все заработки")],
            [KeyboardButton("🗑️ Очистить статистику за сегодня")],
            [KeyboardButton("🔙 Назад в меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "❌ Сброс заработков отменен",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_cancel_reset: {e}")


async def handle_admin_cancel_reset_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена сброса статистики за сегодня"""
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            return

        # Возвращаем админ клавиатуру
        keyboard = [
            [KeyboardButton("📊 Детальная статистика")],
            [KeyboardButton("👥 Пользователи с заработком")],
            [KeyboardButton("🔄 Сбросить все заработки")],
            [KeyboardButton("🗑️ Очистить статистику за сегодня")],
            [KeyboardButton("🔙 Назад в меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "❌ Очистка статистики за сегодня отменена",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"❌ Error in handle_admin_cancel_reset_today: {e}")


# 🔥 ТОП ЗАРАБАТЫВАЮЩИХ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
async def handle_top_earners_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ зарабатывающих для пользователей"""
    try:
        user = update.effective_user

        if not has_access(user.id):
            await update.message.reply_text("❌ Доступ запрещен! Зарегистрируйтесь по реферальной ссылке")
            return

        top_earners = get_top_earners()

        if not top_earners:
            await update.message.reply_text(
                "🏆 *Топ зарабатывающих*\n\n"
                "Пока никто не заработал. Станьте первым! 💪",
                parse_mode='Markdown'
            )
            return

        top_text = "🏆 *Топ зарабатывающих за все время*\n\n"

        for i, earner in enumerate(top_earners[:10], 1):  # Топ-10
            username_display = f"@{earner['username']}" if not earner['username'].startswith(
                'user_') else f"ID: {earner['user_id']}"
            top_text += f"*{i}. {username_display}*\n"
            top_text += f"   🏆 Общий: *{earner['overall_earnings']}$*\n"
            top_text += f"   💰 Личный: {earner['total_earnings']}$\n"
            top_text += f"   👥 Реф: {earner['referral_earnings']}$\n\n"

        # Добавляем информацию о текущем пользователе
        user_data = get_user(user.id)
        if user_data:
            total_earnings = user_data.get("total_earnings", 0)
            referral_earnings = user_data.get("referral_earnings", 0)
            overall_earnings = total_earnings + referral_earnings

            user_position = None
            for i, earner in enumerate(top_earners, 1):
                if earner['user_id'] == user.id:
                    user_position = i
                    break

            if user_position:
                top_text += f"📊 *Ваша позиция:* *{user_position}*\n"
            top_text += f"💰 *Ваш заработок:* *{overall_earnings}$*"

        await update.message.reply_text(top_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"❌ Error in handle_top_earners_button: {e}")
        await update.message.reply_text("❌ Ошибка при получении топа зарабатывающих")


# Обработка кнопки "Назад в меню" в админ панели
async def handle_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            return

        # Возвращаем обычное меню
        keyboard = [
            [KeyboardButton("📱 Сдать номер в аренду")],
            [KeyboardButton("👥 Реферальная система"), KeyboardButton("📊 Моя статистика")],
            [KeyboardButton("💰 Статистика рефералов"), KeyboardButton("🏆 Топ зарабатывающих")],
            [KeyboardButton("ℹ️ Помощь")],
            [KeyboardButton("👑 Админ панель")]
        ]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text("🔙 Возврат в главное меню", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"❌ Error in handle_back_to_menu: {e}")


# Остальные функции остаются без изменений (send_to_user, complete_rental, и т.д.)
# ... [здесь должны быть все остальные функции из предыдущего кода]

# Команда для специального пользователя для отправки сообщений и фото
async def send_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        logger.info(f"📨 Send command received from user {user.id}")

        # Проверяем, является ли пользователь специальным или создателем
        if user.id not in [SPECIAL_USER_ID, CREATOR_CHAT_ID]:
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        # Проверяем, является ли сообщение ответом на сообщение с номером
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Ответьте этой командой на сообщение с номером телефона от бота\n\n"
                "**Как использовать:**\n"
                "1. Найдите сообщение от бота с номером телефона\n"
                "2. Ответьте на него командой:\n"
                "   - `/send Ваш текст` - для текста\n"
                "   - `/send Ваш текст` + фото - для текста с фото\n"
                "   - `/send` + фото - только фото\n\n"
                "**Для завершения аренды и рассчитать платеж:**\n"
                "`/complete 120` - где 120 это минуты простоя"
            )
            return

        reply_message = update.message.reply_to_message
        logger.info(f"🔍 Replying to message ID: {reply_message.message_id}")

        # Ищем rental по message_id (ID сообщения от бота)
        rental = get_rental_by_message_id(reply_message.message_id)
        logger.info(f"🔎 Rental found: {rental}")

        if not rental:
            await update.message.reply_text(
                "❌ Не удалось найти информацию об аренде по этому сообщению.\n"
                "Убедитесь что вы отвечаете на сообщение от бота с номером телефона."
            )
            return

        renter_id = rental[1]  # renter_id из rentals
        phone_number = rental[2]  # phone_number из rentals

        logger.info(f"👤 Renter ID: {renter_id}, Phone: {phone_number}")

        # Проверяем что не пытаемся отправить сообщение самому себе
        if renter_id == user.id:
            await update.message.reply_text("❌ Нельзя отправить сообщение самому себе")
            return

        # Получаем текст сообщения из аргументов команды
        message_text = ' '.join(context.args) if context.args else ""
        logger.info(f"💬 Message text from args: '{message_text}'")

        # Проверяем есть ли прикрепленное фото
        has_photo = update.message.photo is not None and len(update.message.photo) > 0
        logger.info(f"📸 Has photo: {has_photo}")

        if not message_text and not has_photo:
            await update.message.reply_text(
                "❌ Укажите сообщение для отправки пользователю или прикрепите фото\n\n"
                "**Примеры использования:**\n"
                "• `/send Ваш код: 123456` - только текст\n"
                "• `/send Инструкция` + фото - текст с фото\n"
                "• `/send` + фото - только фото с авто-подписью\n"
                "• `/complete 120` - завершить аренду (120 минут)"
            )
            return

        # Добавляем сообщение в pending_messages
        message_type = "photo" if has_photo else "text"
        message_content = message_text or "Фото от администратора"

        logger.info(f"💾 Saving message: type={message_type}, content='{message_content}'")

        message_id = add_pending_message(rental[0], renter_id, message_content, message_type)

        if message_id:
            try:
                if has_photo:
                    # Отправляем фото с подписью
                    photo_file = update.message.photo[-1]
                    logger.info(f"🖼️ Photo file_id: {photo_file.file_id}")

                    caption_text = f"📨 *Сообщение от администратора*\n\n📱 Для номера: `{phone_number}`"

                    if message_text:
                        caption_text += f"\n\n💬 {message_text}"

                    logger.info(f"📝 Photo caption: {caption_text}")

                    # Отправляем фото
                    await context.bot.send_photo(
                        chat_id=renter_id,
                        photo=photo_file.file_id,
                        caption=caption_text,
                        parse_mode='Markdown'
                    )
                    logger.info(f"✅ Photo successfully sent to user {renter_id}")

                else:
                    # Отправляем текстовое сообщение
                    await context.bot.send_message(
                        chat_id=renter_id,
                        text=f"📨 *Сообщение от администратора*\n\n"
                             f"📱 Для номера: `{phone_number}`\n\n"
                             f"💬 {message_text}",
                        parse_mode='Markdown'
                    )
                    logger.info(f"✅ Text message successfully sent to user {renter_id}")

                await update.message.reply_text("✅ Сообщение успешно отправлено пользователю")

            except Exception as e:
                logger.error(f"❌ Error sending message to user {renter_id}: {str(e)}")
                await update.message.reply_text(
                    f"❌ Не удалось отправить сообщение пользователю {renter_id}.\n"
                    f"Ошибка: {str(e)}"
                )
        else:
            await update.message.reply_text("❌ Ошибка при сохранении сообщения в базе данных")

    except Exception as e:
        logger.error(f"❌ Error in send_to_user command: {str(e)}")
        await update.message.reply_text(f"❌ Ошибка при выполнении команды: {str(e)}")


# Команда завершения аренды
async def complete_rental(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        # Проверяем, является ли пользователь специальным
        if user.id not in [SPECIAL_USER_ID, CREATOR_CHAT_ID]:
            await update.message.reply_text("❌ У вас нет доступа к этой команде")
            return

        # Проверяем, является ли сообщение ответом
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Ответьте на сообщение с номером телефона командой:\n"
                "/complete 120 - где 120 это минуты простоя"
            )
            return

        # Получаем количество минут
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "❌ Укажите количество минут\n"
                "Пример: /complete 120"
            )
            return

        try:
            minutes = float(context.args[0])
            if minutes <= 0:
                await update.message.reply_text("❌ Количество минут должно быть больше 0")
                return
        except ValueError:
            await update.message.reply_text("❌ Укажите корректное число минут")
            return

        # Ищем rental
        reply_message = update.message.reply_to_message
        rental = get_rental_by_message_id(reply_message.message_id)

        if not rental:
            await update.message.reply_text("❌ Не найдена информация об аренде")
            return

        rental_id = rental[0]
        renter_id = rental[1]
        phone_number = rental[2]
        referrer_id = rental[5]

        # Рассчитываем заработок
        earnings = minutes * PRICE_PER_MINUTE
        earnings = round(earnings, 2)

        # 🔥 ПРОВЕРКА МИНИМАЛЬНОЙ ВЫПЛАТЫ (3$)
        MINIMUM_PAYOUT = 1.94
        is_payout_eligible = earnings >= MINIMUM_PAYOUT

        # Обновляем аренду ВСЕГДА, даже если сумма маленькая
        if update_rental_earnings(rental_id, minutes, earnings):
            # Обновляем заработок пользователя только если сумма достаточна для выплаты
            if is_payout_eligible:
                update_user_earnings(renter_id, earnings)

            # Уведомляем пользователя
            renter_user = get_user(renter_id)
            renter_name = renter_user.get("username", f"user_{renter_id}") if renter_user else f"user_{renter_id}"

            if is_payout_eligible:
                # 🔥 СУММА ДОСТАТОЧНА ДЛЯ ВЫПЛАТЫ
                await context.bot.send_message(
                    chat_id=renter_id,
                    text=f"💰 Аренда завершена!\n\n"
                         f"📱 Номер: {phone_number}\n"
                         f"⏱ Время простоя: {minutes} минут\n"
                         f"💵 Заработок: {earnings}$\n\n"
                         f"💎 Тариф: {PRICE_PER_MINUTE}$/мин\n"
                         f"✅ Сумма доступна для выплаты"
                )
            else:
                # 🔥 СУММА МАЛЕНЬКАЯ - только отчет
                needed_minutes = math.ceil((MINIMUM_PAYOUT - earnings) / PRICE_PER_MINUTE)
                await context.bot.send_message(
                    chat_id=renter_id,
                    text=f"📊 Отчет по аренде\n\n"
                         f"📱 Номер: {phone_number}\n"
                         f"⏱ Время простоя: {minutes} минут\n"
                         f"💵 Заработок: {earnings}$\n\n"
                         f"💎 Тариф: {PRICE_PER_MINUTE}$/мин\n"
                         f"⚠️ Сумма меньше минимальной выплаты (1.5$)\n"
                         f"💡 Нужно еще: {needed_minutes} минут для выплаты"
                )

            # Уведомляем реферера если есть И сумма достаточна для выплаты
            if referrer_id and is_payout_eligible:
                commission = earnings * 0.1
                commission = round(commission, 2)
                update_user_earnings(referrer_id, 0, commission)

                referrer_user = get_user(referrer_id)
                referrer_name = referrer_user.get("username",
                                                  f"user_{referrer_id}") if referrer_user else f"user_{referrer_id}"

                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 Ваш реферал заработал!\n\n"
                         f"👤 Реферал: {renter_name}\n"
                         f"📱 Номер: {phone_number}\n"
                         f"⏱ Время: {minutes} минут\n"
                         f"💰 Заработок реферала: {earnings}$\n"
                         f"💵 Ваша комиссия (10%): {commission}$"
                )

            # Ответ специальному пользователю
            if is_payout_eligible:
                await update.message.reply_text(
                    f"✅ Аренда завершена!\n\n"
                    f"📱 Номер: {phone_number}\n"
                    f"⏱ Минут: {minutes}\n"
                    f"💰 Заработок: {earnings}$\n"
                    f"👤 Пользователь: {renter_name}\n"
                    f"👥 Реферер: {referrer_name if referrer_id else 'Нет'}\n\n"
                    f"💳 Сумма доступна для выплаты"
                )
            else:
                await update.message.reply_text(
                    f"📊 Отчет отправлен пользователю\n\n"
                    f"📱 Номер: {phone_number}\n"
                    f"⏱ Минут: {minutes}\n"
                    f"💰 Заработок: {earnings}$\n"
                    f"👤 Пользователь: {renter_name}\n\n"
                    f"⚠️ Сумма меньше минимальной выплаты (1.5$)\n"
                    f"💡 Пользователь уведомлен"
                )

            logger.info(f"✅ Rental {rental_id} completed: {minutes}min, ${earnings}, payout: {is_payout_eligible}")

        else:
            await update.message.reply_text("❌ Ошибка при обновлении аренды")

    except Exception as e:
        logger.error(f"❌ Error in complete_rental: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


# Статистика рефералов
async def referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        if not has_access(user.id):
            await update.message.reply_text("❌ Доступ запрещен! Зарегистрируйтесь по реферальной ссылке")
            return

        # Получаем статистику рефералов
        ref_stats = get_referrer_stats(user.id)
        referral_count = ref_stats[0]
        total_commission = ref_stats[1]
        referral_rentals = ref_stats[2]

        # Получаем общую статистику пользователя
        user_data = get_user(user.id)
        total_earnings = user_data.get("total_earnings", 0) if user_data else 0
        referral_earnings = user_data.get("referral_earnings", 0) if user_data else 0
        overall_earnings = total_earnings + referral_earnings

        if referral_count == 0:
            stats_text = "📊 *Статистика рефералов*\n\n"
            stats_text += "У вас еще нет рефералов.\n"
            stats_text += "Приглашайте друзей по реферальной ссылке и получайте 10% от их заработка!\n\n"
            stats_text += f"💵 Ваш общий заработок: *{overall_earnings}$*\n"
            stats_text += f"  ├ Личный: {total_earnings}$\n"
            stats_text += f"  └ С рефералов: {referral_earnings}$"

            await update.message.reply_text(stats_text, parse_mode='Markdown')
            return

        stats_text = f"📊 *Статистика рефералов*\n\n"
        stats_text += f"👥 Всего рефералов: *{referral_count}*\n"
        stats_text += f"💰 Общая комиссия: *{total_commission:.2f}$*\n\n"
        stats_text += f"💵 *Ваш общий заработок:* *{overall_earnings}$*\n"
        stats_text += f"  ├ Личный: {total_earnings}$\n"
        stats_text += f"  └ С рефералов: {referral_earnings}$\n\n"

        if referral_rentals:
            stats_text += "📈 *Аренды рефералов:*\n\n"
            for rental in referral_rentals[:10]:  # Показываем последние 10
                stats_text += (
                    f"👤 @{rental['username']}\n"
                    f"📱 {rental['phone']}\n"
                    f"⏱ {rental['minutes']} мин → {rental['earnings']:.2f}$\n"
                    f"💵 Ваша комиссия: *{rental['commission']:.2f}$*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )

            if len(referral_rentals) > 10:
                stats_text += f"\n... и еще {len(referral_rentals) - 10} аренд"
        else:
            stats_text += "📭 У ваших рефералов еще нет завершенных аренд"

        await update.message.reply_text(stats_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"❌ Error in referral_stats: {e}")
        await update.message.reply_text("❌ Ошибка при получении статистики")


# Обработка кнопки "Сдать номер в аренду"
async def handle_rent_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        # Проверяем доступ пользователя
        if not has_access(user.id):
            await update.message.reply_text("❌ Доступ запрещен! Зарегистрируйтесь по реферальной ссылке")
            return

        await update.message.reply_text(
            f"📱 *Сдача номера в аренду*\n\n"
            f"💰 *Тариф:* {PRICE_PER_MINUTE}$ за минуту\n"
            f"💳 *Минимальная выплата:* 3минуты\n\n"
            "📝 Введите номер телефона в формате:\n"
            "*Российские номера:*\n"
            "• +79123456789\n"
            "• 89123456789\n"
            "• 79123456789\n\n"
            "*Казахстанские номера:*\n"
            "• +77123456789\n"
            "• 87123456789\n"
            "• 77123456789\n\n"
            "После отправки номера он будет автоматически сдан в аренду.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Error in handle_rent_button: {e}")
        await update.message.reply_text("❌ Ошибка при обработке запроса")


# Обработка ввода номера телефона
async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        # Проверяем доступ пользователя
        if not has_access(user.id):
            await update.message.reply_text("❌ Доступ запрещен! Зарегистрируйтесь по реферальной ссылке")
            return

        message_text = update.message.text

        # Проверяем номер телефона
        validated_phone = validate_phone_number(message_text)

        if not validated_phone:
            await update.message.reply_text(
                "❌ Неверный формат номера телефона!\n\n"
                "📱 Пожалуйста, введите номер в одном из форматов:\n"
                "*Российские номера:*\n"
                "• +79123456789\n"
                "• 89123456789\n"
                "• 79123456789\n\n"
                "*Казахстанские номера:*\n"
                "• +77123456789\n"
                "• 87123456789\n"
                "• 77123456789\n\n"
                "Попробуйте еще раз:",
                parse_mode='Markdown'
            )
            return

        # Получаем информацию о реферере
        user_data = get_user(user.id)
        referrer_id = user_data.get("referrer_id") if user_data else None

        # Получаем информацию о реферере для отображения
        referrer_info = ""
        if referrer_id:
            referrer_user = get_user(referrer_id)
            if referrer_user:
                referrer_name = referrer_user.get("username", f"user_{referrer_id}")
                referrer_info = f"👥 Реферер: @{referrer_name} (ID: {referrer_id})"

        # Отправляем номер специальному пользователю (если это не сам пользователь)
        message_id = None
        if SPECIAL_USER_ID != user.id:  # Проверяем что это не сам пользователь
            try:
                # Используем простой текст без Markdown для избежания ошибок
                message_text_to_admin = (
                    f"📱 НОВЫЙ НОМЕР ДЛЯ АРЕНДЫ\n\n"
                    f"👤 Пользователь: @{user.username}\n"
                    f"🆔 User ID: {user.id}\n"
                    f"📞 Номер телефона: {validated_phone}\n"
                    f"💰 Тариф: {PRICE_PER_MINUTE}$/мин\n"
                )

                if referrer_info:
                    message_text_to_admin += f"{referrer_info}\n\n"
                else:
                    message_text_to_admin += "\n"

                message_text_to_admin += (
                    f"💬 Чтобы отправить сообщение пользователю:\n"
                    f"`/send Ваш текст` + фото если нужно\n\n"
                    f"💰 Чтобы завершить аренду и рассчитать платеж:\n"
                    f"`/complete 120` - где 120 это минуты простоя"
                )

                sent_message = await context.bot.send_message(
                    chat_id=SPECIAL_USER_ID,
                    text=message_text_to_admin
                )
                message_id = sent_message.message_id
                logger.info(f"✅ Сообщение отправлено SPECIAL_USER_ID {SPECIAL_USER_ID}, message_id: {message_id}")
            except Exception as e:
                logger.error(f"❌ Error sending message to special user {SPECIAL_USER_ID}: {e}")
                # Не прерываем процесс, продолжаем без message_id
        else:
            logger.info(f"👤 Пользователь {user.id} является SPECIAL_USER_ID, пропускаем отправку")

        # Добавляем аренду в базу данных (без суммы, она будет рассчитана позже)
        rental_id = add_rental(user.id, validated_phone, referrer_id=referrer_id, message_id=message_id)

        if rental_id:
            # Отправляем подтверждение пользователю
            await update.message.reply_text(
                f"✅ *Номер успешно сдан в аренду!*\n\n"
                f"📞 *Номер:* `{validated_phone}`\n"
                f"💰 *Тариф:* {PRICE_PER_MINUTE}$ за минуту\n\n"
                f"📨 Ожидайте сообщение от администратора с дальнейшими инструкциями.\n"
                f"После завершения аренды вы получите расчет платежа.",
                parse_mode='Markdown'
            )

            # Логируем действие
            logger.info(f"✅ Получен номер от {user.id}: {validated_phone}, rental_id: {rental_id}")
        else:
            await update.message.reply_text("❌ Ошибка при сохранении аренды. Попробуйте еще раз.")

    except Exception as e:
        logger.error(f"❌ Error in handle_phone_input: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке номера. Попробуйте еще раз.")


# Команда /ref
async def ref(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_user

        if not has_access(user.id):
            await update.message.reply_text("❌ Доступ запрещен! Зарегистрируйтесь по реферальной ссылке")
            return

        referral_link = generate_referral_link(user.id)

        # Получаем статистику рефералов
        try:
            ref_stats = get_referrer_stats(user.id)
            referral_count = ref_stats[0]
            total_commission = ref_stats[1]
        except Exception as e:
            logger.error(f"❌ Error getting referrer stats: {e}")
            referral_count = 0
            total_commission = 0.0

        keyboard = [
            [InlineKeyboardButton("📤 Поделиться ссылкой",
                                  url=f"tg://msg_url?url={referral_link}&text=Присоединяйся%20к%20аренде%20WhatsApp%20номеров!")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"👥 *Реферальная система*\n\n"
            f"🔗 *Ваша реферальная ссылка:*\n"
            f"`{referral_link}`\n\n"
            f"*Как это работает:*\n"
            f"• Приводите друзей по своей ссылке\n"
            f"• Получаете 10% от их заработка\n"
            f"• Без вашей ссылки люди не смогут пользоваться ботом\n\n"
            f"📊 *Ваша статистика:*\n"
            f"• Рефералов: *{referral_count}*\n"
            f"• Заработано: *{total_commission:.2f}$*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Error in ref: {e}")
        await update.message.reply_text("❌ Ошибка при получении реферальной информации")


# Команда /my_stats
async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        if not has_access(user.id):
            await update.message.reply_text("❌ Доступ запрещен! Зарегистрируйтесь по реферальной ссылке")
            return

        rentals = get_user_rentals(user.id)
        user_data = get_user(user.id)

        total_earnings = user_data.get("total_earnings", 0) if user_data else 0
        referral_earnings = user_data.get("referral_earnings", 0) if user_data else 0
        overall_earnings = total_earnings + referral_earnings

        if not rentals:
            stats_text = "📊 *Ваша статистика*\n\n"
            stats_text += "У вас еще нет сданных номеров.\n"
            stats_text += "Нажмите \"📱 Сдать номер в аренду\" чтобы начать зарабатывать!\n\n"
            stats_text += f"💵 Общий заработок: *{overall_earnings}$*\n"
            stats_text += f"  ├ Личный: {total_earnings}$\n"
            stats_text += f"  └ С рефералов: {referral_earnings}$"

            await update.message.reply_text(stats_text, parse_mode='Markdown')
            return

        total_rentals = len(rentals)
        completed_rentals = [r for r in rentals if r[7] == "completed"]
        total_minutes = sum(rental[9] for rental in completed_rentals if rental[9])

        stats_text = f"📊 *Ваша статистика*\n\n"
        stats_text += f"📈 Всего сдано номеров: *{total_rentals}*\n"

        if completed_rentals:
            stats_text += f"✅ Завершено аренд: *{len(completed_rentals)}*\n"
            stats_text += f"⏱ Общее время аренды: *{total_minutes:.1f} минут*\n\n"

        stats_text += f"💵 *Общий заработок:* *{overall_earnings}$*\n"
        stats_text += f"  ├ Личный: {total_earnings}$\n"
        stats_text += f"  └ С рефералов: {referral_earnings}$\n\n"

        if completed_rentals:
            # Показываем последние 5 аренд
            stats_text += "📋 *Последние аренды:*\n\n"
            for rental in completed_rentals[:5]:
                phone = rental[2]
                minutes = rental[9] or 0
                earnings = rental[4] or 0
                stats_text += f"📱 {phone}\n⏱ {minutes} мин → 💵 {earnings:.2f}$\n━━━━━━━━━━━━━━━━━━━━\n"

        await update.message.reply_text(stats_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"❌ Error in my_stats: {e}")
        await update.message.reply_text("❌ Ошибка при получении статистики")


# Обработка кнопки "Моя статистика"
async def handle_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_stats(update, context)


# Обработка кнопки "Реферальная система"
async def handle_referral_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ref(update, context)


# Обработка кнопки "Статистика рефералов"
async def handle_referral_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await referral_stats(update, context)


# Обработка кнопки "Помощь"
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        if not has_access(user.id):
            await update.message.reply_text("❌ Доступ запрещен! Зарегистрируйтесь по реферальной ссылке")
            return

        help_text = (
            f"ℹ️ *Помощь по боту:*\n\n"
            f"📱 *Как сдать номер в аренду:*\n"
            f"1. Нажмите \"📱 Сдать номер в аренду\"\n"
            f"2. Введите номер в правильном формате\n"
            f"3. Номер автоматически отправляется администратору\n"
            f"4. Ожидайте сообщение с инструкциями\n\n"
            f"📞 *Поддерживаемые форматы номеров:*\n"
            f"*Россия:* +79123456789, 89123456789, 79123456789\n"
            f"*Казахстан:* +77123456789, 87123456789, 77123456789\n\n"
            f"💰 *Тариф:* {PRICE_PER_MINUTE}$ за минуту\n\n"
            f"💳 *Минимальная выплата:* 3минуты\n\n"
            f"👥 *Реферальная система:*\n"
            f"• Только по вашей ссылке люди могут зарегистрироваться\n"
            f"• Получайте 10% от заработка рефералов\n\n"
            f"📊 *Статистика:*\n"
            f"• \"📊 Моя статистика\" - ваши аренды и общий заработок\n"
            f"• \"💰 Статистика рефералов\" - доход с рефералов\n"
            f"• \"🏆 Топ зарабатывающих\" - топ пользователей за все время\n\n"
            f"⚠️ *Важно:* Для работы с ботом необходим username!\n\n"
            f"❓ *По всем вопросам:* @kolprey"
        )

        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Error in help_command: {e}")
        await update.message.reply_text("❌ Ошибка при показе помощи")


# Обработка кнопки "Назад" в админ панели
async def handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user

        if user.id != CREATOR_CHAT_ID:
            return

        # Возвращаем обычное меню
        keyboard = [
            [KeyboardButton("📱 Сдать номер в аренду")],
            [KeyboardButton("👥 Реферальная система"), KeyboardButton("📊 Моя статистика")],
            [KeyboardButton("💰 Статистика рефералов"), KeyboardButton("🏆 Топ зарабатывающих")],
            [KeyboardButton("ℹ️ Помощь")],
            [KeyboardButton("👑 Админ панель")]
        ]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text("🔙 Возврат в главное меню", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"❌ Error in handle_back_button: {e}")


def main():
    try:
        # Инициализируем JSON базу данных
        init_json_db()

        # Создаем администратора если его нет
        ensure_admin_user()

        # Проверим что администратор создан
        data = load_json_data()
        admin_exists = str(CREATOR_CHAT_ID) in data["users"]
        admin_has_access = data["users"].get(str(CREATOR_CHAT_ID), {}).get("has_access", False)

        logger.info(f"🔧 Admin check - Exists: {admin_exists}, Has access: {admin_has_access}")

        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("ref", ref))
        application.add_handler(CommandHandler("my_stats", my_stats))
        application.add_handler(CommandHandler("referral_stats", referral_stats))
        application.add_handler(CommandHandler("send", send_to_user))
        application.add_handler(CommandHandler("complete", complete_rental))
        application.add_handler(CommandHandler("admin", admin_panel))
        application.add_handler(CommandHandler("help", help_command))

        # Обработчики кнопок главного меню
        application.add_handler(MessageHandler(filters.Text("📱 Сдать номер в аренду"), handle_rent_button))
        application.add_handler(MessageHandler(filters.Text("👥 Реферальная система"), handle_referral_button))
        application.add_handler(MessageHandler(filters.Text("📊 Моя статистика"), handle_stats_button))
        application.add_handler(MessageHandler(filters.Text("💰 Статистика рефералов"), handle_referral_stats_button))
        application.add_handler(MessageHandler(filters.Text("🏆 Топ зарабатывающих"), handle_top_earners_button))
        application.add_handler(MessageHandler(filters.Text("ℹ️ Помощь"), help_command))
        application.add_handler(MessageHandler(filters.Text("👑 Админ панель"), admin_panel))

        # 🔥 ОБНОВЛЕННЫЕ ОБРАБОТЧИКИ АДМИН ПАНЕЛИ
        application.add_handler(MessageHandler(filters.Text("📊 Детальная статистика"), handle_admin_detailed_stats))
        application.add_handler(
            MessageHandler(filters.Text("👥 Пользователи с заработком"), handle_admin_users_with_earnings))
        application.add_handler(MessageHandler(filters.Text("🔄 Сбросить все заработки"), handle_admin_reset_earnings))
        application.add_handler(
            MessageHandler(filters.Text("🗑️ Очистить статистику за сегодня"), handle_admin_reset_today_earnings))
        application.add_handler(MessageHandler(filters.Text("✅ Да, сбросить все"), handle_admin_confirm_reset))
        application.add_handler(
            MessageHandler(filters.Text("✅ Да, очистить сегодня"), handle_admin_confirm_reset_today))
        application.add_handler(MessageHandler(filters.Text("❌ Нет, отмена"), handle_admin_cancel_reset))
        application.add_handler(MessageHandler(filters.Text("❌ Нет, отмена"), handle_admin_cancel_reset_today))
        application.add_handler(MessageHandler(filters.Text("🔙 Назад в меню"), handle_back_to_menu))

        # Обработчик ввода номера телефона
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Text(
            ["📱 Сдать номер в аренду", "👥 Реферальная система", "📊 Моя статистика", "💰 Статистика рефералов",
             "🏆 Топ зарабатывающих", "ℹ️ Помощь", "👑 Админ панель",
             "📊 Детальная статистика", "👥 Пользователи с заработком", "🔄 Сбросить все заработки",
             "🗑️ Очистить статистику за сегодня", "✅ Да, сбросить все", "✅ Да, очистить сегодня",
             "❌ Нет, отмена", "🔙 Назад в меню"]),
                                               handle_phone_input))

        # Обработчики для фото
        application.add_handler(MessageHandler(
            filters.PHOTO & filters.CaptionRegex(r'^/send'),
            send_to_user
        ))

        application.add_handler(MessageHandler(
            filters.PHOTO & filters.REPLY,
            send_to_user
        ))

        # Запускаем бота
        print("🤖 Бот запущен с JSON базой данных...")
        logger.info("🤖 Bot started successfully")
        application.run_polling()

    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        print(f"💥 Fatal error: {e}")


if __name__ == "__main__":
    main()