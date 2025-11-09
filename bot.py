import sys
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)
import currency_api
from database import Database

# Устанавливаем кодировку UTF-8 для вывода в консоль Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Загружаем переменные окружения
load_dotenv()

# Состояния для ConversationHandler
WAITING_FROM_COUNTRY, WAITING_TO_COUNTRY, WAITING_RATE_CONFIRM, WAITING_MANUAL_RATE, WAITING_INITIAL_BALANCE = range(5)

# Инициализация базы данных
db = Database()

# Словарь для хранения временных данных пользователей
user_data: Dict[int, Dict] = {}


def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать новое путешествие", callback_data="new_trip")],
        [InlineKeyboardButton("✈️ Мои путешествия", callback_data="my_trips")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("📊 История расходов", callback_data="history")],
        [InlineKeyboardButton("💱 Изменить курс", callback_data="change_rate")]
    ]
    return InlineKeyboardMarkup(keyboard)


def format_balance(balance_from: float, balance_to: float, 
                  currency_from: str, currency_to: str) -> str:
    """Форматирование баланса для отображения"""
    return f"Остаток: {balance_from:,.2f} {currency_from} = {balance_to:,.2f} {currency_to}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    welcome_text = (
        "👋 Добро пожаловать в Travel Wallet!\n\n"
        "Этот бот поможет вам отслеживать расходы во время путешествий.\n\n"
        "Выберите действие из меню:"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "new_trip":
        await new_trip_command(update, context)
    elif data == "my_trips":
        await my_trips_command(update, context)
    elif data == "balance":
        await balance_command(update, context)
    elif data == "history":
        await history_command(update, context)
    elif data == "change_rate":
        await change_rate_command(update, context)
    elif data.startswith("switch_trip_"):
        trip_id = int(data.split("_")[2])
        await switch_trip(update, context, trip_id)
    elif data.startswith("confirm_expense_"):
        parts = data.split("_")
        amount_from = float(parts[2])
        amount_to = float(parts[3])
        await confirm_expense(update, context, amount_from, amount_to)
    elif data.startswith("cancel_expense"):
        await query.edit_message_text("❌ Расход не учтен.", reply_markup=get_main_menu())
    elif data == "main_menu":
        await query.edit_message_text("Главное меню:", reply_markup=get_main_menu())
    elif data == "cancel_rate_change":
        user_id = update.effective_user.id
        if 'changing_rate' in context.user_data:
            del context.user_data['changing_rate']
        await query.edit_message_text("❌ Изменение курса отменено.", reply_markup=get_main_menu())
    elif data == "skip_initial_balance":
        await skip_initial_balance(update, context)


async def new_trip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать создание нового путешествия"""
    user_id = update.effective_user.id
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(
            "✈️ Создание нового путешествия\n\n"
            "Введите страну отправления (например: Россия):"
        )
    else:
        await update.message.reply_text(
            "✈️ Создание нового путешествия\n\n"
            "Введите страну отправления (например: Россия):"
        )
    
    user_data[user_id] = {}
    return WAITING_FROM_COUNTRY


async def process_from_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка страны отправления"""
    user_id = update.effective_user.id
    from_country = update.message.text.strip()
    
    user_data[user_id]["from_country"] = from_country
    
    await update.message.reply_text(
        f"📍 Страна отправления: {from_country}\n\n"
        "Введите страну назначения (например: Китай):"
    )
    
    return WAITING_TO_COUNTRY


async def process_to_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка страны назначения и проверка валют"""
    user_id = update.effective_user.id
    to_country = update.message.text.strip()
    
    user_data[user_id]["to_country"] = to_country
    
    from_country = user_data[user_id]["from_country"]
    
    # Получаем список валют через API
    currencies_result = currency_api.get_supported_currencies()
    
    if not currencies_result['success']:
        await update.message.reply_text(
            f"❌ Ошибка при получении списка валют: {currencies_result.get('error', 'Неизвестная ошибка')}\n\n"
            "Попробуйте еще раз позже.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END
    
    currencies = currencies_result['currencies']
    
    # Простая логика определения валюты по стране (можно улучшить)
    # Для примера используем базовые валюты
    country_to_currency = {
        "россия": "RUB", "russia": "RUB",
        "китай": "CNY", "china": "CNY",
        "сша": "USD", "usa": "USD", "америка": "USD",
        "европа": "EUR", "europe": "EUR", "германия": "EUR", "germany": "EUR",
        "великобритания": "GBP", "uk": "GBP", "britain": "GBP",
        "япония": "JPY", "japan": "JPY",
        "турция": "TRY", "turkey": "TRY",
        "тайланд": "THB", "thailand": "THB",
        "дубай": "AED", "uae": "AED", "оаэ": "AED"
    }
    
    from_country_lower = from_country.lower()
    to_country_lower = to_country.lower()
    
    from_currency = country_to_currency.get(from_country_lower, "RUB")
    to_currency = country_to_currency.get(to_country_lower, "USD")
    
    # Проверяем, что валюты поддерживаются
    if from_currency not in currencies and from_currency not in currency_api.SUPPORTED_CURRENCIES:
        from_currency = "RUB"  # По умолчанию
    
    if to_currency not in currencies and to_currency not in currency_api.SUPPORTED_CURRENCIES:
        to_currency = "USD"  # По умолчанию
    
    user_data[user_id]["from_currency"] = from_currency
    user_data[user_id]["to_currency"] = to_currency
    
    # Получаем текущий курс через API
    await update.message.reply_text(
        f"🔄 Получаю текущий курс обмена...\n"
        f"Из: {from_currency}\n"
        f"В: {to_currency}"
    )
    
    # Конвертируем 1 единицу для получения курса
    conversion_result = currency_api.convert_currency(from_currency, to_currency, 1)
    
    if not conversion_result.get('success'):
        await update.message.reply_text(
            f"❌ Ошибка при получении курса: {conversion_result.get('error', 'Неизвестная ошибка')}\n\n"
            "Введите курс обмена вручную (например: 0.128 для 1 CNY = 0.128 RUB):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_new_trip")
            ]])
        )
        return WAITING_MANUAL_RATE
    
    rate = conversion_result.get('result')
    if rate:
        rate = float(rate)
    else:
        # Пытаемся получить курс из info
        info = conversion_result.get('info', {})
        rate = info.get('rate', 1.0)
        if rate:
            rate = float(rate)
        else:
            rate = 1.0
    
    user_data[user_id]["rate"] = rate
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, подходит", callback_data="confirm_rate")],
        [InlineKeyboardButton("❌ Нет, ввести вручную", callback_data="manual_rate")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_new_trip")]
    ]
    
    await update.message.reply_text(
        f"📊 Текущий курс обмена:\n\n"
        f"1 {from_currency} = {rate:.6f} {to_currency}\n\n"
        f"Этот курс подходит?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return WAITING_RATE_CONFIRM


async def confirm_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение курса и запрос начальной суммы"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Ошибка: данные не найдены.", reply_markup=get_main_menu())
        return ConversationHandler.END
    
    data = user_data[user_id]
    from_currency = data["from_currency"]
    to_currency = data["to_currency"]
    rate = data["rate"]
    
    keyboard = [[InlineKeyboardButton("❌ Пропустить (начать с 0)", callback_data="skip_initial_balance")]]
    
    await query.edit_message_text(
        f"✅ Курс установлен: 1 {from_currency} = {rate:.6f} {to_currency}\n\n"
        f"Введите начальную сумму в валюте {from_currency} (например: 1000):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return WAITING_INITIAL_BALANCE


async def manual_rate_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода курса вручную"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Введите курс обмена вручную (например: 0.128 для 1 CNY = 0.128 RUB):"
    )
    
    return WAITING_MANUAL_RATE


async def process_manual_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного курса"""
    user_id = update.effective_user.id
    
    try:
        rate = float(update.message.text.replace(",", "."))
        if rate <= 0:
            raise ValueError("Курс должен быть положительным числом")
        
        user_data[user_id]["rate"] = rate
        
        # Запрашиваем начальную сумму
        data = user_data[user_id]
        from_currency = data["from_currency"]
        
        keyboard = [[InlineKeyboardButton("❌ Пропустить (начать с 0)", callback_data="skip_initial_balance")]]
        
        await update.message.reply_text(
            f"✅ Курс установлен: 1 {from_currency} = {rate:.6f} {data['to_currency']}\n\n"
            f"Введите начальную сумму в валюте {from_currency} (например: 1000):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return WAITING_INITIAL_BALANCE
        
    except ValueError as e:
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)}\n\n"
            "Введите курс обмена вручную (например: 0.128):"
        )
        return WAITING_MANUAL_RATE


async def process_initial_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенной начальной суммы"""
    user_id = update.effective_user.id
    
    try:
        initial_balance = float(update.message.text.replace(",", "."))
        if initial_balance < 0:
            raise ValueError("Сумма не может быть отрицательной")
        
        # Создаем путешествие с начальной суммой
        data = user_data[user_id]
        from_country = data["from_country"]
        to_country = data["to_country"]
        from_currency = data["from_currency"]
        to_currency = data["to_currency"]
        rate = data["rate"]
        
        trip_name = f"{from_country} → {to_country}"
        
        trip_id = db.create_trip(
            user_id=user_id,
            name=trip_name,
            from_country=from_country,
            to_country=to_country,
            from_currency=from_currency,
            to_currency=to_currency,
            exchange_rate=rate,
            initial_balance=initial_balance
        )
        
        initial_balance_to = initial_balance * rate
        
        await update.message.reply_text(
            f"✅ Путешествие создано!\n\n"
            f"📍 {trip_name}\n"
            f"💱 Курс: 1 {from_currency} = {rate:.6f} {to_currency}\n"
            f"💰 Начальный баланс: {initial_balance:.2f} {from_currency} = {initial_balance_to:.2f} {to_currency}\n\n"
            f"Теперь вы можете вводить суммы расходов, и бот будет автоматически конвертировать их.",
            reply_markup=get_main_menu()
        )
        
        del user_data[user_id]
        return ConversationHandler.END
        
    except ValueError as e:
        keyboard = [[InlineKeyboardButton("❌ Пропустить (начать с 0)", callback_data="skip_initial_balance")]]
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)}\n\n"
            f"Введите начальную сумму в валюте {user_data[user_id]['from_currency']} (например: 1000):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_INITIAL_BALANCE


async def skip_initial_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск начальной суммы (начать с 0)"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Ошибка: данные не найдены.", reply_markup=get_main_menu())
        return ConversationHandler.END
    
    # Создаем путешествие с нулевым балансом
    data = user_data[user_id]
    from_country = data["from_country"]
    to_country = data["to_country"]
    from_currency = data["from_currency"]
    to_currency = data["to_currency"]
    rate = data["rate"]
    
    trip_name = f"{from_country} → {to_country}"
    
    trip_id = db.create_trip(
        user_id=user_id,
        name=trip_name,
        from_country=from_country,
        to_country=to_country,
        from_currency=from_currency,
        to_currency=to_currency,
        exchange_rate=rate,
        initial_balance=0
    )
    
    await query.edit_message_text(
        f"✅ Путешествие создано!\n\n"
        f"📍 {trip_name}\n"
        f"💱 Курс: 1 {from_currency} = {rate:.6f} {to_currency}\n"
        f"💰 Начальный баланс: 0 {from_currency}\n\n"
        f"Теперь вы можете вводить суммы расходов, и бот будет автоматически конвертировать их.",
        reply_markup=get_main_menu()
    )
    
    del user_data[user_id]
    return ConversationHandler.END


async def cancel_new_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания путешествия"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    await query.edit_message_text(
        "❌ Создание путешествия отменено.",
        reply_markup=get_main_menu()
    )
    
    return ConversationHandler.END


async def my_trips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список путешествий"""
    user_id = update.effective_user.id
    trips = db.get_all_trips(user_id)
    
    if not trips:
        text = "📭 У вас пока нет путешествий.\n\nСоздайте новое путешествие, чтобы начать отслеживать расходы."
        if isinstance(update, Update) and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())
        else:
            await update.message.reply_text(text, reply_markup=get_main_menu())
        return
    
    keyboard = []
    text = "✈️ Ваши путешествия:\n\n"
    
    for trip in trips:
        status = "✅ Активно" if trip['is_active'] else ""
        text += f"{status} {trip['name']}\n"
        text += f"   💱 {trip['from_currency']} → {trip['to_currency']}\n"
        text += f"   💰 {format_balance(trip['balance_from'], trip['balance_to'], trip['from_currency'], trip['to_currency'])}\n\n"
        
        if not trip['is_active']:
            keyboard.append([InlineKeyboardButton(
                f"🔄 Активировать: {trip['name']}",
                callback_data=f"switch_trip_{trip['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def switch_trip(update: Update, context: ContextTypes.DEFAULT_TYPE, trip_id: int):
    """Переключить активное путешествие"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if db.switch_active_trip(user_id, trip_id):
        trip = db.get_trip(trip_id, user_id)
        await query.edit_message_text(
            f"✅ Активное путешествие изменено на: {trip['name']}\n\n"
            f"Теперь все расходы будут учитываться для этого путешествия.",
            reply_markup=get_main_menu()
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при переключении путешествия.",
            reply_markup=get_main_menu()
        )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс"""
    user_id = update.effective_user.id
    trip = db.get_active_trip(user_id)
    
    if not trip:
        text = "❌ У вас нет активного путешествия.\n\nСоздайте новое путешествие или активируйте существующее."
        if isinstance(update, Update) and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())
        else:
            await update.message.reply_text(text, reply_markup=get_main_menu())
        return
    
    balance_text = format_balance(
        trip['balance_from'],
        trip['balance_to'],
        trip['from_currency'],
        trip['to_currency']
    )
    
    text = (
        f"💰 Баланс путешествия:\n\n"
        f"📍 {trip['name']}\n"
        f"{balance_text}\n\n"
        f"💱 Курс: 1 {trip['from_currency']} = {trip['exchange_rate']:.6f} {trip['to_currency']}"
    )
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())
    else:
        await update.message.reply_text(text, reply_markup=get_main_menu())


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю расходов"""
    user_id = update.effective_user.id
    trip = db.get_active_trip(user_id)
    
    if not trip:
        text = "❌ У вас нет активного путешествия."
        if isinstance(update, Update) and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())
        else:
            await update.message.reply_text(text, reply_markup=get_main_menu())
        return
    
    expenses = db.get_expenses(trip['id'], user_id, limit=10)
    
    if not expenses:
        text = f"📊 История расходов для {trip['name']}:\n\nПока нет расходов."
    else:
        text = f"📊 История расходов для {trip['name']}:\n\n"
        for expense in expenses:
            # amount_from - в домашней валюте (from_currency)
            # amount_to - в валюте пребывания (to_currency)
            text += f"💸 {expense['amount_to']:.2f} {trip['to_currency']} = {expense['amount_from']:.2f} {trip['from_currency']}\n"
            if expense['description']:
                text += f"   📝 {expense['description']}\n"
            text += f"   📅 {expense['created_at']}\n\n"
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())
    else:
        await update.message.reply_text(text, reply_markup=get_main_menu())


async def change_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить курс обмена"""
    user_id = update.effective_user.id
    trip = db.get_active_trip(user_id)
    
    if not trip:
        text = "❌ У вас нет активного путешествия."
        if isinstance(update, Update) and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())
        else:
            await update.message.reply_text(text, reply_markup=get_main_menu())
        return
    
    text = (
        f"💱 Изменение курса для {trip['name']}\n\n"
        f"Текущий курс: 1 {trip['from_currency']} = {trip['exchange_rate']:.6f} {trip['to_currency']}\n\n"
        f"Введите новый курс обмена (например: 0.128):"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_rate_change")]]
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    context.user_data['changing_rate'] = trip['id']
    return "WAITING_NEW_RATE"


async def process_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нового курса"""
    user_id = update.effective_user.id
    
    try:
        new_rate = float(update.message.text.replace(",", "."))
        if new_rate <= 0:
            raise ValueError("Курс должен быть положительным числом")
        
        trip_id = context.user_data.get('changing_rate')
        if not trip_id:
            await update.message.reply_text("❌ Ошибка: путешествие не найдено.", reply_markup=get_main_menu())
            return ConversationHandler.END
        
        if db.update_exchange_rate(trip_id, user_id, new_rate):
            trip = db.get_trip(trip_id, user_id)
            await update.message.reply_text(
                f"✅ Курс обновлен!\n\n"
                f"Новый курс: 1 {trip['from_currency']} = {new_rate:.6f} {trip['to_currency']}\n\n"
                f"{format_balance(trip['balance_from'], trip['balance_to'], trip['from_currency'], trip['to_currency'])}",
                reply_markup=get_main_menu()
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении курса.", reply_markup=get_main_menu())
        
        del context.user_data['changing_rate']
        return ConversationHandler.END
        
    except ValueError as e:
        keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_rate_change")]]
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)}\n\n"
            "Введите курс обмена (например: 0.128):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return "WAITING_NEW_RATE"


async def handle_number_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщения с числом (расход)"""
    # Пропускаем, если пользователь в процессе создания путешествия или изменения курса
    if context.user_data.get('changing_rate') or update.effective_user.id in user_data:
        return
    
    user_id = update.effective_user.id
    trip = db.get_active_trip(user_id)
    
    if not trip:
        return  # Не показываем сообщение, если нет активного путешествия
    
    try:
        # Пытаемся извлечь число из сообщения
        text = update.message.text.strip()
        
        # Проверяем, что это похоже на число (только цифры, точка, запятая, возможно пробелы)
        if not re.match(r'^[\d\s.,]+$', text):
            return  # Не число, игнорируем
        
        # Удаляем все символы кроме цифр, точки и запятой
        cleaned = re.sub(r'[^\d.,]', '', text)
        if not cleaned:
            return
        
        cleaned = cleaned.replace(',', '.')
        
        # Проверяем, что это действительно число
        # Введенное число - это сумма в валюте страны назначения (пребывания)
        amount_in_destination = float(cleaned)
        
        if amount_in_destination <= 0:
            return
        
        # Конвертируем из валюты страны назначения (to_currency) в домашнюю валюту (from_currency)
        conversion_result = currency_api.convert_currency(
            trip['to_currency'],  # Из валюты пребывания
            trip['from_currency'],  # В домашнюю валюту
            amount_in_destination
        )
        
        if not conversion_result.get('success'):
            # Используем сохраненный курс (обратный)
            # Курс хранится как 1 from_currency = rate to_currency
            # Значит 1 to_currency = 1/rate from_currency
            amount_in_home = amount_in_destination / trip['exchange_rate']
        else:
            amount_in_home = conversion_result.get('result', amount_in_destination / trip['exchange_rate'])
            if amount_in_home:
                amount_in_home = float(amount_in_home)
            else:
                amount_in_home = amount_in_destination / trip['exchange_rate']
        
        # Сохраняем временные данные для подтверждения
        # amount_from - в домашней валюте (from_currency)
        # amount_to - в валюте пребывания (to_currency)
        context.user_data['pending_expense'] = {
            'amount_from': amount_in_home,
            'amount_to': amount_in_destination
        }
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Да", callback_data=f"confirm_expense_{amount_in_home}_{amount_in_destination}"),
                InlineKeyboardButton("❌ Нет", callback_data="cancel_expense")
            ]
        ]
        
        await update.message.reply_text(
            f"💸 {amount_in_destination:.2f} {trip['to_currency']} = {amount_in_home:.2f} {trip['from_currency']}\n\n"
            f"Учесть как расход?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except (ValueError, InvalidOperation):
        # Не число, игнорируем
        pass


async def confirm_expense(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         amount_from: float, amount_to: float):
    """Подтверждение расхода"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    trip = db.get_active_trip(user_id)
    
    if not trip:
        await query.edit_message_text("❌ Ошибка: путешествие не найдено.", reply_markup=get_main_menu())
        return
    
    # Добавляем расход
    # amount_from - в домашней валюте (from_currency)
    # amount_to - в валюте пребывания (to_currency)
    db.add_expense(trip['id'], user_id, amount_from, amount_to)
    
    # Получаем обновленный баланс
    balance = db.get_balance(trip['id'], user_id)
    
    await query.edit_message_text(
        f"✅ Расход учтен!\n\n"
        f"💸 {amount_to:.2f} {trip['to_currency']} = {amount_from:.2f} {trip['from_currency']}\n\n"
        f"{format_balance(balance[0], balance[1], trip['from_currency'], trip['to_currency'])}",
        reply_markup=get_main_menu()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    user_id = update.effective_user.id
    if 'changing_rate' in context.user_data:
        del context.user_data['changing_rate']
    
    await update.message.reply_text("Операция отменена.", reply_markup=get_main_menu())
    return ConversationHandler.END


async def cancel_rate_change_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены изменения курса"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if 'changing_rate' in context.user_data:
        del context.user_data['changing_rate']
    
    await query.edit_message_text("❌ Изменение курса отменено.", reply_markup=get_main_menu())
    return ConversationHandler.END


def main():
    """Главная функция запуска бота"""
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден в .env файле")
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # ConversationHandler для создания путешествия
    trip_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("newtrip", new_trip_command),
            CallbackQueryHandler(new_trip_command, pattern="^new_trip$")
        ],
        states={
            WAITING_FROM_COUNTRY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_from_country)
            ],
            WAITING_TO_COUNTRY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_to_country)
            ],
            WAITING_RATE_CONFIRM: [
                CallbackQueryHandler(confirm_rate, pattern="^confirm_rate$"),
                CallbackQueryHandler(manual_rate_input, pattern="^manual_rate$"),
                CallbackQueryHandler(cancel_new_trip, pattern="^cancel_new_trip$")
            ],
            WAITING_MANUAL_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_rate)
            ],
            WAITING_INITIAL_BALANCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_initial_balance),
                CallbackQueryHandler(skip_initial_balance, pattern="^skip_initial_balance$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel_new_trip, pattern="^cancel_new_trip$")]
    )
    
    # ConversationHandler для изменения курса
    rate_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("setrate", change_rate_command),
            CallbackQueryHandler(change_rate_command, pattern="^change_rate$")
        ],
        states={
            "WAITING_NEW_RATE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_rate)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_rate_change_handler, pattern="^cancel_rate_change$")
        ]
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("switch", my_trips_command))
    application.add_handler(trip_conv_handler)
    application.add_handler(rate_conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик чисел (расходы) - должен быть последним
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number_message))
    
    # Запускаем бота
    print("🤖 Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

