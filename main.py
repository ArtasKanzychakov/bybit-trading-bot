import os
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
                maxBytes=5*1024*1024,  # 5 MB
                backupCount=3,
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    # Уменьшаем логирование для внешних библиотек
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
user_sessions: dict[int, dict[str, Any]] = {}

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
        
        balance = await trade_engine.get_balance(force_update=True)
        logger.info(f"Current balance for {user.id}: {balance:.2f} USDT")
        
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я бот для автоматической торговли на Bybit.\n"
            f"Текущий баланс: {balance:.2f} USDT\n\n"
            "Нажмите '📊 Начать настройку', чтобы выбрать стратегию и пару.",
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
    
    try:
        balance = await trade_engine.get_balance(force_update=True)
        logger.info(f"User {user_id} balance: {balance:.2f} USDT")
        
        if balance < 5:
            await update.message.reply_text(
                f"⚠ Ваш баланс ({balance:.2f} USDT) слишком мал для торговли.\n"
                "Минимальный рекомендуемый депозит: 10 USDT",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END
        
        settings = get_user_settings(user_id)
        keyboard = [
            ["📈 Стратегия 1 (Bollinger)"],
            ["📉 Стратегия 2 (EMA Cross)"],
            ["⬅ Назад", "🔝 В начало", "🛑 Остановить торги"]
        ]
        
        default_strategy = settings[1] if settings else None
        message = f"Баланс: {balance:.2f} USDT\nВыберите торговую стратегию:"
        if default_strategy:
            message += f"\n(Текущая по умолчанию: {default_strategy})"
        
        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        return CHOOSE_STRATEGY
        
    except Exception as e:
        logger.error(f"Begin setup error for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "Ошибка при проверке баланса. Попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

# ... (остальные обработчики остаются без изменений, как в вашем исходном коде) ...

async def show_status(update: Update, context: CallbackContext):
    try:
        status = trade_engine.get_status()
        balance = await trade_engine.get_balance(force_update=True)
        open_trades = get_open_trades()
        
        logger.info(f"Status requested. Balance: {balance:.2f} USDT")
        
        message = f"💰 Баланс: {balance:.2f} USDT\n{status}"
        if open_trades:
            message += "\n\n📌 Открытые сделки:\n"
            for trade in open_trades:
                message += (
                    f"ID: {trade[0]}, {trade[2]} @ {trade[3]}, "
                    f"Объем: {trade[5]}, Вход: {trade[6]}\n"
                )
        
        await update.message.reply_text(
            message, 
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Status error: {e}", exc_info=True)
        await update.message.reply_text(
            "Ошибка при получении статуса.",
            reply_markup=main_menu_keyboard()
        )

async def send_heartbeat(context: ContextTypes.DEFAULT_TYPE):
    try:
        status = trade_engine.get_status()
        balance = await trade_engine.get_balance(force_update=True)
        logger.info(f"Heartbeat sent. Balance: {balance:.2f} USDT")
        
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"❤️ Heartbeat\nБаланс: {balance:.2f} USDT\n{status}",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Heartbeat error: {e}", exc_info=True)

def main():
    try:
        logger.info("Starting bot initialization...")
        
        app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

        # Настройка обработчиков
        states = {
            CHOOSE_STRATEGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_strategy)],
            CHOOSE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_symbol)],
            SET_RISK: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_risk)],
            SET_LEVERAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_leverage)],
            CONFIRM_RUN: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_run)],
        }

        fallbacks = [
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🛑 Остановить торги$"), stop_trading),
            MessageHandler(filters.Regex("^📊 Начать настройку$"), begin_setup)
        ]

        conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^📊 Начать настройку$"), begin_setup)],
            states=states,
            fallbacks=fallbacks
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv_handler)
        app.add_handler(MessageHandler(filters.Regex("^📈 Статус$"), show_status))
        app.add_handler(MessageHandler(filters.Regex("^📋 История сделок$"), show_history))
        app.add_handler(MessageHandler(filters.Regex("^🛑 Остановить торги$"), stop_trading))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

        # Планировщик задач
        if ADMIN_CHAT_ID:
            app.job_queue.run_repeating(send_heartbeat, interval=3600, first=10)

        # Запуск бота
        if WEBHOOK_URL and WEBHOOK_SECRET:
            logger.info("Starting webhook...")
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=WEBHOOK_SECRET,
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
