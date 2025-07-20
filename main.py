import logging
import os
from dotenv import load_dotenv
from flask import Flask, request

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
    Dispatcher,
)

from utils import get_balance
from trade_engine import start_trading, stop_trading
import ccxt

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or "webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # полный адрес, например https://your-app.onrender.com/webhook
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__)
bot = Bot(TELEGRAM_TOKEN)

application = Application.builder().token(TELEGRAM_TOKEN).build()

# Состояния
CHOOSE_SYMBOL, CHOOSE_TIMEFRAME, MAIN_MENU = range(3)

ALLOWED_SYMBOLS = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]
ALLOWED_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"]

def get_bybit_account():
    return ccxt.bybit({
        "apiKey": os.getenv("BYBIT_API_KEY_REAL"),
        "secret": os.getenv("BYBIT_API_SECRET_REAL"),
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это бот для торговли на Bybit.\nВыберите валютную пару:",
        reply_markup=ReplyKeyboardMarkup([ALLOWED_SYMBOLS], one_time_keyboard=True),
    )
    return CHOOSE_SYMBOL

async def choose_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text.strip()
    if symbol not in ALLOWED_SYMBOLS:
        await update.message.reply_text("Неверный выбор. Повторите.")
        return CHOOSE_SYMBOL

    context.user_data["symbol"] = symbol
    await update.message.reply_text(
        "Выберите таймфрейм:",
        reply_markup=ReplyKeyboardMarkup([ALLOWED_TIMEFRAMES], one_time_keyboard=True),
    )
    return CHOOSE_TIMEFRAME

async def choose_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    timeframe = update.message.text.strip()
    if timeframe not in ALLOWED_TIMEFRAMES:
        await update.message.reply_text("Неверный выбор. Повторите.")
        return CHOOSE_TIMEFRAME

    context.user_data["timeframe"] = timeframe
    try:
        context.user_data["exchange"] = get_bybit_account()
    except Exception as e:
        logger.error(f"Ошибка подключения к Bybit: {e}")
        await update.message.reply_text("Ошибка подключения к бирже.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Пара: {context.user_data['symbol']}, Таймфрейм: {timeframe}\n"
        "Доступные команды:\n"
        "/balance — баланс\n"
        "/start_trade — начать\n"
        "/stop_trade — остановить\n"
        "/cancel — отменить",
        reply_markup=ReplyKeyboardRemove(),
    )
    return MAIN_MENU

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exchange = context.user_data.get("exchange")
    if not exchange:
        await update.message.reply_text("Сначала выполните /start.")
        return
    try:
        balance_info = get_balance(exchange)
        await update.message.reply_text(balance_info)
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        await update.message.reply_text("Ошибка при получении баланса.")

async def start_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exchange = context.user_data.get("exchange")
    symbol = context.user_data.get("symbol")
    tf = context.user_data.get("timeframe")
    if not all([exchange, symbol, tf]):
        await update.message.reply_text("Сначала выполните /start.")
        return
    await update.message.reply_text(f"🚀 Торговля началась: {symbol} [{tf}]")
    # Блокирующую функцию в фоновый поток
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, start_trading, exchange, symbol, tf)

async def stop_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stop_trading()
        await update.message.reply_text("🛑 Торговля остановлена.")
    except Exception as e:
        logger.error(f"Ошибка остановки: {e}")
        await update.message.reply_text("Ошибка при остановке.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Диалог завершён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CHOOSE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_symbol)],
        CHOOSE_TIMEFRAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_timeframe)],
        MAIN_MENU: [
            CommandHandler("balance", balance),
            CommandHandler("start_trade", start_trade),
            CommandHandler("stop_trade", stop_trade),
            CommandHandler("cancel", cancel),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True,
)

application.add_handler(conv_handler)
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CommandHandler("start_trade", start_trade))
application.add_handler(CommandHandler("stop_trade", stop_trade))
application.add_handler(CommandHandler("cancel", cancel))

@app.route(f"/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

if __name__ == "__main__":
    # Установка webhook при старте
    bot.delete_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}")
    logger.info(f"Webhook установлен: {WEBHOOK_URL}/{WEBHOOK_SECRET}")
    app.run(host="0.0.0.0", port=PORT)
