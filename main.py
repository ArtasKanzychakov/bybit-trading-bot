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
from trade_engine import start_trading, stop_trading
import ccxt

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHOOSE_SYMBOL, CHOOSE_TIMEFRAME, MAIN_MENU = range(3)

user_data_store = {}

def get_bybit_account():
    return ccxt.bybit({
        "apiKey": os.getenv("BYBIT_API_KEY_REAL"),
        "secret": os.getenv("BYBIT_API_SECRET_REAL"),
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    context.user_data["exchange"] = get_bybit_account()

    await update.message.reply_text(
        f"✅ Пара: {context.user_data['symbol']}, Таймфрейм: {context.user_data['timeframe']}\n"
        f"Команды:\n"
        f"/balance — показать баланс\n"
        f"/start_trade — начать торговлю\n"
        f"/stop_trade — остановить торговлю\n"
        f"/cancel — отменить",
        reply_markup=ReplyKeyboardRemove(),
    )
    return MAIN_MENU


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exchange = context.user_data.get("exchange")
    if not exchange:
        await update.message.reply_text("Сначала запустите /start")
        return
    balance_info = get_balance(exchange)
    await update.message.reply_text(balance_info)


async def start_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exchange = context.user_data.get("exchange")
    symbol = context.user_data.get("symbol")
    tf = context.user_data.get("timeframe")

    if not all([exchange, symbol, tf]):
        await update.message.reply_text("Пожалуйста, выберите пару и таймфрейм через /start")
        return

    await update.message.reply_text(f"🚀 Торговля началась для {symbol} [{tf}]")
    start_trading(exchange, symbol, tf)


async def stop_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stop_trading()
    await update.message.reply_text("🛑 Торговля остановлена.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_symbol)],
            CHOOSE_TIMEFRAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_timeframe)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("start_trade", start_trade))
    app.add_handler(CommandHandler("stop_trade", stop_trade))
    app.add_handler(CommandHandler("cancel", cancel))

    app.run_polling()


if __name__ == "__main__":
    main()
