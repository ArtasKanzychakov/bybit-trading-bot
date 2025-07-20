import os
import hmac
import hashlib
import time
import json
import aiohttp
from typing import Optional, Dict, Any, List

class BybitAPI:
    BASE_URL = 'https://api.bybit.com'
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = aiohttp.ClientSession()

    def _sign_request(self, params: Dict[str, Any]) -> str:
        """Подписывает запрос с использованием API секрета"""
        param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False) -> Dict:
        """Выполняет HTTP запрос к API Bybit"""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if signed:
            if params is None:
                params = {}
            params['api_key'] = self.api_key
            params['timestamp'] = int(time.time() * 1000)
            params['sign'] = self._sign_request(params)
        
        try:
            async with self.session.request(
                method, url, params=params, headers=headers
            ) as response:
                data = await response.json()
                if data.get('ret_code') != 0:
                    raise Exception(f"API error: {data.get('ret_msg')}")
                return data.get('result', {})
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

    async def get_klines(self, symbol: str, interval: str = '5m', limit: int = 100) -> List[Dict]:
        """Получает исторические данные свечей"""
        endpoint = '/public/linear/kline'
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        return await self._request('GET', endpoint, params)

    async def get_balance(self) -> Dict[str, Any]:
        """Получает баланс аккаунта"""
        endpoint = '/v2/private/wallet/balance'
        return await self._request('GET', endpoint, signed=True)

    async def place_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float, 
        price: Optional[float] = None,
        order_type: str = 'Market'
    ) -> Dict[str, Any]:
        """Размещает ордер на бирже"""
        endpoint = '/private/linear/order/create'
        params = {
            'symbol': symbol,
            'side': side.capitalize(),
            'order_type': order_type,
            'qty': quantity,
            'time_in_force': 'GoodTillCancel',
            'reduce_only': False,
            'close_on_trigger': False
        }
        
        if price is not None:
            params['price'] = price
            params['order_type'] = 'Limit'
        
        return await self._request('POST', endpoint, params, signed=True)

    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """Закрывает все позиции по символу"""
        endpoint = '/private/linear/order/create'
        params = {
            'symbol': symbol,
            'side': 'Sell' if self.position == 'long' else 'Buy',
            'order_type': 'Market',
            'qty': self.position_size,
            'time_in_force': 'GoodTillCancel',
            'reduce_only': True,
            'close_on_trigger': True
        }
        return await self._request('POST', endpoint, params, signed=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
