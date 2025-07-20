import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from dotenv import load_dotenv
from trade_engine import TradeEngine

load_dotenv()

TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', '5000'))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

trade_engine = TradeEngine()

# Состояния
CHOOSE_STRATEGY, CHOOSE_SYMBOL = range(2)

# Хранилище пользовательских выборов
user_state = {}  # user_id: {strategy: ..., symbol: ...}

# Доступные пары
available_pairs = ["SOLUSDT", "BTCUSDT", "ETHUSDT", "XRPUSDT", "DOGEUSDT"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Выбрать стратегию"],
        ["Выбрать пару"],
        ["Запустить торговлю", "Остановить торговлю"],
        ["Статус"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот для автоматической торговли на Bybit.\n"
        "Выберите действие с помощью кнопок ниже.",
        reply_markup=reply_markup
    )

async def choose_strategy_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Стратегия 1"], ["Стратегия 2"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите стратегию:", reply_markup=reply_markup)
    return CHOOSE_STRATEGY

async def set_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    strategy = update.message.text
    user_id = update.effective_user.id
    user_state.setdefault(user_id, {})["strategy"] = strategy
    await update.message.reply_text(f"Вы выбрали {strategy}")
    return ConversationHandler.END

async def choose_symbol_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["SOLUSDT", "BTCUSDT"], ["ETHUSDT", "XRPUSDT"], ["DOGEUSDT"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите валютную пару:", reply_markup=reply_markup)
    return CHOOSE_SYMBOL

async def set_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text
    user_id = update.effective_user.id
    user_state.setdefault(user_id, {})["symbol"] = symbol
    await update.message.reply_text(f"Вы выбрали {symbol}")
    return ConversationHandler.END

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    state = user_state.get(user_id, {})

    if text == "Выбрать стратегию":
        return await choose_strategy_prompt(update, context)

    if text == "Выбрать пару":
        return await choose_symbol_prompt(update, context)

    if text == "Запустить торговлю":
        strategy = state.get("strategy", "Стратегия 2")
        symbol = state.get("symbol", "SOLUSDT")
        started = trade_engine.start_strategy(symbol, strategy)
        if started:
            await update.message.reply_text(f"Торговля запущена: {symbol} ({strategy})")
        else:
            await update.message.reply_text("Торговля уже идёт.")

    if text == "Остановить торговлю":
        trade_engine.stop_strategy()
        await update.message.reply_text("Торговля остановлена.")

    if text == "Статус":
        await update.message.reply_text(trade_engine.get_status())

def main():
    app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Выбрать стратегию$"), choose_strategy_prompt)],
        states={CHOOSE_STRATEGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_strategy)]},
        fallbacks=[]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Выбрать пару$"), choose_symbol_prompt)],
        states={CHOOSE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_symbol)]},
        fallbacks=[]
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_SECRET,
        webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}"
    )

if __name__ == "__main__":
    main()
