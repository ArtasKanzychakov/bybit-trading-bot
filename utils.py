def get_balance(exchange):
    try:
        balance = exchange.fetch_balance()
        usdt = balance['total'].get('USDT', 0)
        return f"💰 Баланс: {usdt:.2f} USDT"
    except Exception as e:
        return f"Ошибка получения баланса: {str(e)}"
