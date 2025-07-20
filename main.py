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

# Состояния для ConversationHandler
CHOOSE_STRATEGY, CHOOSE_SYMBOL, CONFIRM_RUN = range(3)

trade_engine = TradeEngine()
user_state = {}  # user_id: {strategy: ..., symbol: ...}

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [["Начать настройку"], ["Статус"]],
        resize_keyboard=True
    )

def back_menu_keyboard():
    return ReplyKeyboardMarkup(
        [["⬅ Назад"], ["🔝 В начало"]],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для автоматической торговли на Bybit.\nНажмите 'Начать настройку', чтобы выбрать стратегию и пару.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ---------- Шаг 1: Выбор стратегии ----------
async def begin_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Стратегия 1"], ["Стратегия 2"], ["⬅ Назад", "🔝 В начало"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите торговую стратегию:", reply_markup=reply_markup)
    return CHOOSE_STRATEGY

async def set_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад" or text == "🔝 В начало":
        return await start(update, context)

    user_state.setdefault(user_id, {})["strategy"] = text
    keyboard = [["SOLUSDT", "BTCUSDT"], ["ETHUSDT", "XRPUSDT"], ["DOGEUSDT"], ["⬅ Назад", "🔝 В начало"]]
    await update.message.reply_text(f"Стратегия выбрана: {text}\nТеперь выберите валютную пару:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CHOOSE_SYMBOL

# ---------- Шаг 2: Выбор пары ----------
async def set_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await begin_setup(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)

    user_state.setdefault(user_id, {})["symbol"] = text
    keyboard = [["🚀 Запустить торговлю"], ["⬅ Назад", "🔝 В начало"]]
    await update.message.reply_text(
        f"Пара выбрана: {text}\nГотово к запуску!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CONFIRM_RUN

# ---------- Шаг 3: Подтверждение запуска ----------
async def confirm_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await set_strategy(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)

    strategy = user_state[user_id].get("strategy", "Стратегия 2")
    symbol = user_state[user_id].get("symbol", "SOLUSDT")
    started = trade_engine.start_strategy(symbol, strategy)

    if started:
        await update.message.reply_text(f"✅ Торговля запущена: {symbol} ({strategy})", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("⚠ Торговля уже запущена.", reply_markup=main_menu_keyboard())

    return ConversationHandler.END

# ---------- Общие действия ----------
async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = trade_engine.get_status()
    await update.message.reply_text(status)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Не понял команду. Нажмите кнопку или /start", reply_markup=main_menu_keyboard())

def main():
    app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Начать настройку$"), begin_setup)],
        states={
            CHOOSE_STRATEGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_strategy)],
            CHOOSE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_symbol)],
            CONFIRM_RUN: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_run)],
        },
        fallbacks=[MessageHandler(filters.COMMAND, unknown)]
    ))

    app.add_handler(MessageHandler(filters.Regex("^Статус$"), show_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_SECRET,
        webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}"
    )

if __name__ == "__main__":
    main()
