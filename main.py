import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from dotenv import load_dotenv
from utils import get_balance
import ccxt

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

CHOOSE_MODE, CHOOSE_SYMBOL, CHOOSE_TIMEFRAME, MAIN_MENU = range(4)

user_data_store = {}  # Хранит текущие сессии пользователей


def get_bybit_account(real_mode: bool):
    if real_mode:
        return ccxt.bybit({
            "apiKey": os.getenv("BYBIT_API_KEY_REAL"),
            "secret": os.getenv("BYBIT_API_SECRET_REAL"),
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
    else:
        return ccxt.bybit({
            "apiKey": os.getenv("BYBIT_API_KEY_TEST"),
            "secret": os.getenv("BYBIT_API_SECRET_TEST"),
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
            "urls": {"api": {"public": "https://api-testnet.bybit.com", "private": "https://api-testnet.bybit.com"}},
        })


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["🟢 Реальный счёт", "🧪 Тестовый счёт"]]
    await update.message.reply_text(
        "Выберите режим работы:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return CHOOSE_MODE


async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = update.message.text
    real_mode = mode == "🟢 Реальный счёт"
    context.user_data["real_mode"] = real_mode
    context.user_data["exchange"] = get_bybit_account(real_mode)
    reply_keyboard = [["BTC/USDT", "ETH/USDT", "XRP/USDT"]]
    await update.message.reply_text(
        "Выберите валютную пару:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return CHOOSE_SYMBOL


async def choose_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["symbol"] = update.message.text
    reply_keyboard = [["1m", "5m", "15m", "1h", "4h"]]
    await update.message.reply_text(
        "Выберите таймфрейм:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return CHOOSE_TIMEFRAME


async def choose_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["timeframe"] = update.message.text
    symbol = context.user_data["symbol"]
    tf = context.user_data["timeframe"]

    await update.message.reply_text(
        f"✅ Готово! Пара: {symbol}, Таймфрейм: {tf}\n\n"
        f"Отправьте /balance — чтобы проверить баланс\n"
        f"Отправьте /start — чтобы перезапустить настройки.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return MAIN_MENU


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exchange = context.user_data.get("exchange")
    if not exchange:
        await update.message.reply_text("Сначала запустите бота через /start.")
        return
    balance_info = get_balance(exchange)
    await update.message.reply_text(balance_info)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_mode)],
            CHOOSE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_symbol)],
            CHOOSE_TIMEFRAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_timeframe)],
            MAIN_MENU: [CommandHandler("balance", balance)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_ha_
