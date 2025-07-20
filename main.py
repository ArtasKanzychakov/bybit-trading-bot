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

load_dotenv()

required_env_vars = ['TELEGRAM_API_KEY', 'BYBIT_API_KEY', 'BYBIT_API_SECRET']
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Необходимо установить переменную окружения {var}")

TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', '5000'))
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSE_STRATEGY, CHOOSE_SYMBOL, SET_RISK, SET_LEVERAGE, CONFIRM_RUN = range(5)

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
        balance = await trade_engine.get_balance()
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я бот для автоматической торговли на Bybit.\n"
            f"Текущий баланс: {balance:.2f} USDT\n\n"
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
    balance = await trade_engine.get_balance()
    
    if balance < 5:  # Минимальный баланс 5 USDT (~450 руб)
        await update.message.reply_text(
            f"⚠ Ваш баланс ({balance:.2f} USDT) слишком мал для торговли большинством пар.\n"
            "Минимальный рекомендуемый депозит: 10 USDT (~900 руб)",
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
    
    balance = await trade_engine.get_balance()
    if balance < 10:  # Для баланса <10 USDT показываем только дешевые пары
        keyboard = [
            ["SOLUSDT", "XRPUSDT"],
            ["ADAUSDT", "DOGEUSDT"],
            ["⬅ Назад", "🔝 В начало", "🛑 Остановить торги"]
        ]
    else:
        keyboard = [
            ["BTCUSDT", "ETHUSDT"],
            ["SOLUSDT", "XRPUSDT"],
            ["ADAUSDT", "DOGEUSDT"],
            ["⬅ Назад", "🔝 В начало", "🛑 Остановить торги"]
        ]
    
    message = f"Баланс: {balance:.2f} USDT\nВыбрана стратегия: {strategy}\nВыберите валютную пару:"
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
            
            await update.message.reply_text(
                "Выберите кредитное плечо (2x-10x):",
                reply_markup=ReplyKeyboardMarkup(
                    [["2x", "5x", "10x"], ["⬅ Назад", "🔝 В начало"]],
                    resize_keyboard=True
                )
            )
            return SET_LEVERAGE
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

async def set_leverage(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await set_risk(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)

    try:
        leverage = int(text.strip('x'))
        if 2 <= leverage <= 10:
            user_sessions[user_id]["leverage"] = leverage
            
            strategy = user_sessions[user_id].get("strategy")
            symbol = user_sessions[user_id].get("symbol")
            risk = user_sessions[user_id].get("risk")
            
            keyboard = [["✅ Запустить торговлю"], ["⬅ Назад", "🔝 В начало"]]
            await update.message.reply_text(
                f"<b>Подтвердите настройки:</b>\n\n"
                f"🏷 Стратегия: <code>{strategy}</code>\n"
                f"📌 Пара: <code>{symbol}</code>\n"
                f"⚠ Риск: <code>{risk*100}%</code> на сделку\n"
                f"↔ Плечо: <code>{leverage}x</code>",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode='HTML'
            )
            return CONFIRM_RUN
        else:
            await update.message.reply_text(
                "Плечо должно быть между 2x и 10x. Попробуйте снова:",
                reply_markup=ReplyKeyboardMarkup(
                    [["2x", "5x", "10x"], ["⬅ Назад", "🔝 В начало"]],
                    resize_keyboard=True
                )
            )
            return SET_LEVERAGE
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, выберите плечо из предложенных вариантов:",
            reply_markup=ReplyKeyboardMarkup(
                [["2x", "5x", "10x"], ["⬅ Назад", "🔝 В начало"]],
                resize_keyboard=True
            )
        )
        return SET_LEVERAGE

async def confirm_run(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "⬅ Назад":
        return await set_leverage(update, context)
    elif text == "🔝 В начало":
        return await start(update, context)

    session = user_sessions.get(user_id, {})
    strategy = session.get("strategy", "Стратегия 2")
    symbol = session.get("symbol", "BTCUSDT")
    risk = session.get("risk", 0.01)
    leverage = session.get("leverage", 5)
    
    update_user_settings(user_id, strategy=strategy, symbol=symbol, risk=risk, leverage=leverage)
    
    started = trade_engine.start_strategy(symbol, strategy, risk, leverage)
    if started:
        await update.message.reply_text(
            f"✅ Торговля запущена:\n"
            f"Стратегия: <code>{strategy}</code>\n"
            f"Пара: <code>{symbol}</code>\n"
            f"Риск: <code>{risk*100}%</code>\n"
            f"Плечо: <code>{leverage}x</code>",
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
    balance = await trade_engine.get_balance()
    open_trades = get_open_trades()
    
    message = f"💰 Баланс: {balance:.2f} USDT\n{status}"
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

async def send_heartbeat(context: ContextTypes.DEFAULT_TYPE):
    status = trade_engine.get_status()
    balance = await trade_engine.get_balance()
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"❤️ Heartbeat\nБаланс: {balance:.2f} USDT\n{status}",
        parse_mode='HTML'
    )

def main():
    try:
        app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

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

        if WEBHOOK_URL and ADMIN_CHAT_ID:
            app.job_queue.run_repeating(send_heartbeat, interval=3600, first=10)

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
