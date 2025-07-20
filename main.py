import os
import logging
from typing import Dict, Any
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackContext
)
from dotenv import load_dotenv
from trade_engine import TradeEngine
from db import get_user_settings, update_user_settings, get_open_trades, get_trade_history

# Загрузка и проверка переменных окружения
load_dotenv()

required_env_vars = ['TELEGRAM_API_KEY', 'BYBIT_API_KEY', 'BYBIT_API_SECRET']
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Необходимо установить переменную окружения {var}")

TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', '5000'))

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
CHOOSE_STRATEGY, CHOOSE_SYMBOL, SET_RISK, CONFIRM_RUN = range(4)

trade_engine = TradeEngine()
user_sessions: Dict[int, Dict[str, Any]] = {}

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [["📊 Начать настройку", "🛑 Остановить торги"], 
         ["📈 Статус", "📋 История сделок"]],
        resize_keyboard=True
    )

def back_menu_keyboard():
    return ReplyKeyboardMarkup(
        [["⬅ Назад"], ["🔝 В начало", "🛑 Остановить торги"]],
        resize_keyboard=True
    )

async def start(update: Update, context: CallbackContext):
    try:
        user = update.effective_user
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я бот для автоматической торговли на Bybit.\n"
            "Нажмите '📊 Начать настройку', чтобы выбрать стратегию и пару.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

async def begin_setup(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)
    
    keyboard = [
        ["📈 Стратегия 1 (Bollinger)"],
        ["📉 Стратегия 2 (EMA Cross)"],
        ["⬅ Назад", "🔝 В начало", "🛑 Остановить торги"]
    ]
    
    default_strategy = settings[1] if settings else None
    message = "Выберите торговую стратегию:"
    if default_strategy:
        message += f"\n(Текущая по умолчанию: {default_strategy})"
    
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSE_STRATEGY

async def set_strategy(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await start(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)
    elif text == "🛑 Остановить торги":
        return await stop_trading(update, context)

    strategy = "Стратегия 1" if "1" in text else "Стратегия 2"
    user_sessions[user_id] = {"strategy": strategy}
    
    settings = get_user_settings(user_id)
    default_symbol = settings[2] if settings else None
    
    keyboard = [
        ["BTCUSDT", "ETHUSDT"],
        ["SOLUSDT", "XRPUSDT"],
        ["⬅ Назад", "🔝 В начало", "🛑 Остановить торги"]
    ]
    
    message = f"Выбрана стратегия: {strategy}\nТеперь выберите валютную пару:"
    if default_symbol:
        message += f"\n(Текущая по умолчанию: {default_symbol})"
    
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSE_SYMBOL

async def set_symbol(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await begin_setup(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)
    elif text == "🛑 Остановить торги":
        return await stop_trading(update, context)

    user_sessions[user_id]["symbol"] = text
    
    await update.message.reply_text(
        "Укажите уровень риска на сделку (в % от депозита, 0.1-5%):",
        reply_markup=ReplyKeyboardMarkup(
            [["1%", "2%", "3%"], ["⬅ Назад", "🔝 В начало"]],
            resize_keyboard=True
        )
    )
    return SET_RISK

async def set_risk(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await set_strategy(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)

    try:
        risk = float(text.strip('%')) / 100
        if 0.001 <= risk <= 0.05:
            user_sessions[user_id]["risk"] = risk
            
            strategy = user_sessions[user_id].get("strategy")
            symbol = user_sessions[user_id].get("symbol")
            
            keyboard = [["✅ Запустить торговлю"], ["⬅ Назад", "🔝 В начало"]]
            await update.message.reply_text(
                f"<b>Подтвердите настройки:</b>\n\n"
                f"🏷 Стратегия: <code>{strategy}</code>\n"
                f"📌 Пара: <code>{symbol}</code>\n"
                f"⚠ Риск: <code>{risk*100}%</code> на сделку",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode='HTML'
            )
            return CONFIRM_RUN
        else:
            await update.message.reply_text(
                "Риск должен быть между 0.1% и 5%. Попробуйте снова:",
                reply_markup=ReplyKeyboardMarkup(
                    [["1%", "2%", "3%"], ["⬅ Назад", "🔝 В начало"]],
                    resize_keyboard=True
                )
            )
            return SET_RISK
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число от 0.1 до 5 с символом % или без:",
            reply_markup=ReplyKeyboardMarkup(
                [["1%", "2%", "3%"], ["⬅ Назад", "🔝 В начало"]],
                resize_keyboard=True
            )
        )
        return SET_RISK

async def confirm_run(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await set_symbol(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)

    session = user_sessions.get(user_id, {})
    strategy = session.get("strategy", "Стратегия 2")
    symbol = session.get("symbol", "BTCUSDT")
    risk = session.get("risk", 0.01)
    
    # Сохраняем настройки пользователя
    update_user_settings(user_id, strategy=strategy, symbol=symbol, risk=risk)
    
    started = trade_engine.start_strategy(symbol, strategy, risk)
    if started:
        await update.message.reply_text(
            f"✅ Торговля запущена:\n"
            f"Стратегия: <code>{strategy}</code>\n"
            f"Пара: <code>{symbol}</code>\n"
            f"Рик: <code>{risk*100}%</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "⚠ Торговля уже запущена.",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END

async def stop_trading(update: Update, context: CallbackContext):
    stopped = trade_engine.stop_strategy()
    if stopped:
        await update.message.reply_text(
            "✅ Торговля успешно остановлена.",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "ℹ Торговля не была запущена.",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END

async def show_status(update: Update, context: CallbackContext):
    status = trade_engine.get_status()
    open_trades = get_open_trades()
    
    message = status
    if open_trades:
        message += "\n\n📌 Открытые сделки:\n"
        for trade in open_trades:
            message += (
                f"ID: {trade[0]}, {trade[2]} @ {trade[3]}, "
                f"Объем: {trade[5]}, Вход: {trade[6]}\n"
            )
    
    await update.message.reply_text(message, reply_markup=main_menu_keyboard())

async def show_history(update: Update, context: CallbackContext):
    trades = get_trade_history(limit=10)
    if not trades:
        await update.message.reply_text(
            "История сделок пуста.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    message = "📋 Последние 10 сделок:\n\n"
    for trade in trades:
        status = "🟢" if trade[9] == "open" else "🔴"
        profit = f"{trade[8]:.2f}%" if trade[8] is not None else "N/A"
        message += (
            f"{status} {trade[1]}: {trade[2]} @ {trade[3]} → {trade[4] or 'N/A'} "
            f"(Прибыль: {profit})\n"
        )
    
    await update.message.reply_text(message, reply_markup=main_menu_keyboard())

async def unknown(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Не понял команду. Нажмите кнопку или /start",
        reply_markup=main_menu_keyboard()
    )

# ... (исходный код остается без изменений до функции main())

def main():
    try:
        app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

        # Добавляем heartbeat для мониторинга
        async def send_heartbeat(context: ContextTypes.DEFAULT_TYPE):
            status = trade_engine.get_status()
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=f"❤️ Heartbeat\n{status}",
                parse_mode='HTML'
            )

        # Добавляем ping для поддержания активности на Render
        async def ping_self(context: ContextTypes.DEFAULT_TYPE):
            if WEBHOOK_URL:
                try:
                    async with aiohttp.ClientSession() as session:
                        await session.get(WEBHOOK_URL)
                except Exception as e:
                    logger.error(f"Ping failed: {e}")

        # Остальной код инициализации...
        conv_handler = ConversationHandler(...)
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv_handler)
        # ... другие обработчики

        # Запускаем фоновые задачи
        if WEBHOOK_URL:
            app.job_queue.run_repeating(
                send_heartbeat, 
                interval=3600, 
                first=10,
                chat_id=ADMIN_CHAT_ID  # Добавьте ваш chat_id
            )
            app.job_queue.run_repeating(ping_self, interval=300)

        if WEBHOOK_URL and WEBHOOK_SECRET:
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=WEBHOOK_SECRET,
                webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}"
            )
        else:
            logger.info("Запуск в режиме polling")
            app.run_polling()

    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    main()
