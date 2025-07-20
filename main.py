import os
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот для автоматической торговли на Bybit.\n"
                                    "Используй команды /trade, /stop, /status.")

async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /trade <пара>")
        return
    symbol = args[0].upper()
    success = trade_engine.start_strategy(symbol)
    if success:
        await update.message.reply_text(f"Запущена торговля по паре {symbol}")
    else:
        await update.message.reply_text(f"Не удалось запустить торговлю по паре {symbol}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trade_engine.stop_strategy()
    await update.message.reply_text("Торговля остановлена.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = trade_engine.get_status()
    await update.message.reply_text(status)

def main():
    app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trade", trade))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))

    # Настройка webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_SECRET,
        webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}"
    )

if __name__ == "__main__":
    main()
