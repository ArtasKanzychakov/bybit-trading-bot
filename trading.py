import os
import hmac
import hashlib
import time
import json
import aiohttp
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class BybitAPI:
    BASE_URL = 'https://api.bybit.com'
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._session = None
        self.leverage = 5
        self.initialized = False

    async def initialize(self):
        """Явная инициализация соединения"""
        if not self.initialized:
            self._session = aiohttp.ClientSession()
            self.initialized = True
            logger.info("API подключение инициализировано")

    @property
    async def session(self):
        if self._session is None or self._session.closed:
            await self.initialize()
        return self._session

    def _sign_request(self, params: Dict[str, Any]) -> str:
        param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False) -> Dict:
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'X-BAPI-RECV-WINDOW': '5000',
            'X-BAPI-TIMESTAMP': str(int(time.time() * 1000))
        }
        
        if signed:
            if params is None:
                params = {}
            params['api_key'] = self.api_key
            params['timestamp'] = int(time.time() * 1000)
            params['sign'] = self._sign_request(params)
        
        try:
            session = await self.session
            async with session.request(
                method, url, params=params, headers=headers
            ) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    logger.error(f"API error {response.status}: {response_text}")
                    raise Exception(f"API returned {response.status}: {response_text}")
                
                try:
                    data = json.loads(response_text)
                    if data.get('retCode') != 0 and data.get('ret_code') != 0:
                        msg = data.get('retMsg') or data.get('ret_msg', 'Unknown error')
                        logger.error(f"API error: {msg}")
                        raise Exception(f"API error: {msg}")
                    return data.get('result', data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {response_text}")
                    raise Exception(f"Invalid JSON response: {response_text}")
                    
        except Exception as e:
            logger.error(f"Request failed: {str(e)}", exc_info=True)
            raise

    async def get_balance(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        endpoint = '/v5/account/wallet-balance'
        params = params or {}
        params.update({
            'accountType': 'UNIFIED',
            'coin': 'USDT'
        })
        return await self._request('GET', endpoint, params, signed=True)

    # ... остальные методы без изменений ...

    async def get_balance(self) -> Dict[str, Any]:
        endpoint = '/v5/account/wallet-balance'
        params = {
            'accountType': 'UNIFIED',
            'coin': 'USDT'
        }
        return await self._request('GET', endpoint, params, signed=True)

    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a specific symbol"""
        if leverage < 2 or leverage > 10:
            raise ValueError("Leverage must be between 2x and 10x")
            
        endpoint = '/private/linear/position/set-leverage'
        params = {
            'symbol': symbol,
            'buy_leverage': leverage,
            'sell_leverage': leverage
        }
        self.leverage = leverage
        return await self._request('POST', endpoint, params, signed=True)

    async def place_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float, 
        price: Optional[float] = None,
        order_type: str = 'Market',
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None
    ) -> Dict[str, Any]:
        endpoint = '/private/linear/order/create'
        params = {
            'symbol': symbol,
            'side': side.capitalize(),
            'order_type': order_type,
            'qty': quantity,
            'time_in_force': 'GoodTillCancel',
            'reduce_only': False,
            'close_on_trigger': False,
            'is_isolated': True,
            'leverage': self.leverage
        }
        
        if price is not None:
            params['price'] = price
            params['order_type'] = 'Limit'
        
        if take_profit:
            params['take_profit'] = take_profit
        if stop_loss:
            params['stop_loss'] = stop_loss
        
        return await self._request('POST', endpoint, params, signed=True)

    async def close_position(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        endpoint = '/private/linear/order/create'
        params = {
            'symbol': symbol,
            'side': side,
            'order_type': 'Market',
            'qty': quantity,
            'time_in_force': 'GoodTillCancel',
            'reduce_only': True,
            'close_on_trigger': True,
            'is_isolated': True,
            'leverage': self.leverage
        }
        return await self._request('POST', endpoint, params, signed=True)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
