import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Dict
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackContext
)
from dotenv import load_dotenv
from trade_engine import TradeEngine
from db import get_user_settings, update_user_settings, get_open_trades, get_trade_history

# Настройка логирования
def setup_logging():
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            RotatingFileHandler(
                'bot.log',
                maxBytes=5*1024*1024,
                backupCount=3,
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

# Инициализация
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# Проверка переменных окружения
required_env_vars = ['TELEGRAM_API_KEY', 'BYBIT_API_KEY', 'BYBIT_API_SECRET']
for var in required_env_vars:
    if not os.getenv(var):
        logger.critical(f"Missing environment variable: {var}")
        raise ValueError(f"Необходимо установить переменную окружения {var}")

TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', '5000'))
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

# Состояния диалога
CHOOSE_STRATEGY, CHOOSE_SYMBOL, SET_RISK, SET_LEVERAGE, CONFIRM_RUN = range(5)

# Глобальные объекты
trade_engine = TradeEngine()
user_sessions: Dict[int, Dict[str, Any]] = {}

# Клавиатуры
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

# Обработчики команд
async def start(update: Update, context: CallbackContext):
    try:
        user = update.effective_user
        logger.info(f"User {user.id} started the bot")
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я бот для автоматической торговли.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Start command error: {e}", exc_info=True)
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

async def begin_setup(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} began setup")
    await update.message.reply_text(
        "Выберите торговую стратегию:",
        reply_markup=ReplyKeyboardMarkup(
            [["📈 Стратегия 1"], ["📉 Стратегия 2"], ["⬅ Назад"]],
            resize_keyboard=True
        )
    )
    return CHOOSE_STRATEGY

async def set_strategy(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "⬅ Назад":
        return await start(update, context)
    
    user_sessions[user_id] = {"strategy": text}
    await update.message.reply_text(
        "Выберите торговую пару:",
        reply_markup=ReplyKeyboardMarkup(
            [["BTCUSDT", "ETHUSDT"], ["SOLUSDT", "XRPUSDT"], ["⬅ Назад"]],
            resize_keyboard=True
        )
    )
    return CHOOSE_SYMBOL

async def set_symbol(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "⬅ Назад":
        return await begin_setup(update, context)
    
    user_sessions[user_id]["symbol"] = text
    await update.message.reply_text(
        "Укажите уровень риска (1-5%):",
        reply_markup=ReplyKeyboardMarkup(
            [["1%", "2%", "3%"], ["⬅ Назад"]],
            resize_keyboard=True
        )
    )
    return SET_RISK

async def set_risk(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "⬅ Назад":
        return await set_strategy(update, context)
    
    try:
        risk = float(text.strip('%')) / 100
        user_sessions[user_id]["risk"] = risk
        await update.message.reply_text(
            "Выберите плечо:",
            reply_markup=ReplyKeyboardMarkup(
                [["2x", "5x", "10x"], ["⬅ Назад"]],
                resize_keyboard=True
            )
        )
        return SET_LEVERAGE
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число от 1 до 5 с символом %")
        return SET_RISK

async def set_leverage(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "⬅ Назад":
        return await set_risk(update, context)
    
    try:
        leverage = int(text.strip('x'))
        user_sessions[user_id]["leverage"] = leverage
        await update.message.reply_text(
            "Подтвердите настройки:",
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Запустить"], ["⬅ Назад"]],
                resize_keyboard=True
            )
        )
        return CONFIRM_RUN
    except ValueError:
        await update.message.reply_text("Пожалуйста, выберите плечо из предложенных вариантов")
        return SET_LEVERAGE

async def confirm_run(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "⬅ Назад":
        return await set_leverage(update, context)
    
    session = user_sessions.get(user_id, {})
    strategy = session.get("strategy", "Стратегия 1")
    symbol = session.get("symbol", "BTCUSDT")
    risk = session.get("risk", 0.01)
    leverage = session.get("leverage", 5)
    
    started = trade_engine.start_strategy(symbol, strategy, risk, leverage)
    if started:
        await update.message.reply_text(
            "✅ Торговля запущена!",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "⚠ Не удалось запустить стратегию",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END

async def stop_trading(update: Update, context: CallbackContext):
    stopped = trade_engine.stop_strategy()
    if stopped:
        await update.message.reply_text(
            "✅ Торговля остановлена",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "ℹ Торговля не была запущена",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END

async def show_status(update: Update, context: CallbackContext):
    status = trade_engine.get_status()
    await update.message.reply_text(
        status,
        reply_markup=main_menu_keyboard()
    )

async def show_history(update: Update, context: CallbackContext):
    trades = get_trade_history(limit=5)
    message = "Последние сделки:\n" + "\n".join([f"{t[2]} {t[3]}" for t in trades])
    await update.message.reply_text(
        message,
        reply_markup=main_menu_keyboard()
    )

async def unknown(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Неизвестная команда",
        reply_markup=main_menu_keyboard()
    )

def main():
    try:
        logger.info("Starting bot...")
        app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

        conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^📊 Начать настройку$"), begin_setup)],
            states={
                CHOOSE_STRATEGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_strategy)],
                CHOOSE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_symbol)],
                SET_RISK: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_risk)],
                SET_LEVERAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_leverage)],
                CONFIRM_RUN: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_run)],
            },
            fallbacks=[
                CommandHandler("start", start),
                MessageHandler(filters.Regex("^🛑 Остановить торги$"), stop_trading)
            ]
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv_handler)
        app.add_handler(MessageHandler(filters.Regex("^📈 Статус$"), show_status))
        app.add_handler(MessageHandler(filters.Regex("^📋 История сделок$"), show_history))
        app.add_handler(MessageHandler(filters.Regex("^🛑 Остановить торги$"), stop_trading))
        app.add_handler(MessageHandler(filters.TEXT, unknown))

        if WEBHOOK_URL and WEBHOOK_SECRET:
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}"
            )
        else:
            logger.info("Starting polling...")
            app.run_polling()

    except Exception as e:
        logger.critical(f"Bot crashed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
