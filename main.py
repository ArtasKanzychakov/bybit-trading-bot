import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Dict
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackContext, TypeHandler
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
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

# Инициализация
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# Проверка переменных окружения
required_env_vars = ['TELEGRAM_API_KEY']
for var in required_env_vars:
    if not os.getenv(var):
        logger.critical(f"Missing environment variable: {var}")
        raise ValueError(f"Необходимо установить переменную окружения {var}")

TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'default_secret')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', '5000'))

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

async def log_update(update: Update, context: CallbackContext):
    """Логирует входящие обновления"""
    logger.info(f"Incoming update: {update.update_id}")

async def start(update: Update, context: CallbackContext):
    try:
        user = update.effective_user
        logger.info(f"User {user.id} started conversation")
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я бот для автоматической торговли.",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in start: {e}", exc_info=True)

async def handle_webhook_error(update: Update, context: CallbackContext):
    """Обработчик ошибок вебхука"""
    logger.error(f"Webhook error: {context.error}")

def create_application():
    """Создает и настраивает приложение"""
    application = ApplicationBuilder().token(TELEGRAM_API_KEY).build()
    
    # Базовые обработчики
    application.add_handler(TypeHandler(Update, log_update))
    application.add_error_handler(handle_webhook_error)

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # Здесь добавьте остальные обработчики...
    
    return application

async def setup_webhook(application):
    """Настройка вебхука"""
    if not WEBHOOK_URL or not WEBHOOK_SECRET:
        return False
    
    webhook_url = f"{WEBHOOK_URL}/{WEBHOOK_SECRET}"
    logger.info(f"Setting webhook to: {webhook_url}")
    
    try:
        await application.bot.delete_webhook()
        await application.bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True
        )
        logger.info("Webhook configured successfully")
        return True
    except Exception as e:
        logger.critical(f"Failed to set webhook: {e}")
        return False

async def run_application():
    """Основная функция запуска приложения"""
    try:
        application = create_application()
        
        if WEBHOOK_URL and WEBHOOK_SECRET:
            if await setup_webhook(application):
                await application.run_webhook(
                    listen="0.0.0.0",
                    port=PORT,
                    webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}",
                    secret_token=WEBHOOK_SECRET
                )
            else:
                logger.warning("Falling back to polling mode")
                await application.run_polling()
        else:
            logger.info("Starting in polling mode")
            await application.run_polling()
            
    except Exception as e:
        logger.critical(f"Bot crashed: {e}", exc_info=True)
        raise

def main():
    """Точка входа"""
    import asyncio
    
    # Создаем новую event loop для избежания конфликтов
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_application())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        loop.close()

if __name__ == "__main__":
    main()
