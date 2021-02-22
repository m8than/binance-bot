import os
from BInfoTicker import BInfoTicker
from Pair import Pair
import Trade
import json
import time
from binance.enums import *
from pathlib import Path

class Account:
    def __init__(self, binance_client, binfoticker, logger):
        self.binance_client = binance_client
        self.trades = []
        self.updateData()
        self.binfoticker = binfoticker
        self.logger = logger
        self.is_saving = False
        self.realised_profit_session = 0
        self.loadCurrentSessionProfit()
    
    def updateBinanceClient(self, binance_client):
        self.binance_client = binance_client

    def tradeExists(self, symbol):
        for trade in self.trades:
            if trade.buy_pair.symbol.lower() == symbol.lower():
                return True
        return False

    def deleteTrade(self, symbol):
        for i in range(len(self.trades)):
            if self.trades[i].buy_pair.symbol == symbol:
                del self.trades[i]
                self.saveTrades()
                break
        return

    def buy(self, pair, quote_asset_amount, long_term = False, setup_safety_oco = True):
        client = self.binance_client

        bought = False
        attempts = 0
        orderId = None

        price = pair.last_price
        quantity = round(quote_asset_amount, pair.quantity_precision)
        while not bought:
            attempts += 1
            if attempts > 10:
                return None
            
            price = pair.last_price
            order = client.order_market(
                symbol=pair.symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_LIMIT,
                quoteOrderQty=quantity,
                newOrderRespType=ORDER_RESP_TYPE_FULL
                )
            prices = []
            for fill in order['fills']:
                prices.append(float(fill['price']))
            price = sum(prices) / len(prices)

            quantity = order['executedQty']

            if 'orderId' not in order:
                continue
            orderId = order['orderId']

            # check if it's filled
            for i in range(10):
                try:
                    order_info = self.binance_client.get_order(symbol=pair.symbol, orderId=orderId)
                    if order_info['status'] == 'FILLED':
                        bought = True
                        break
                except:
                    pass
                time.sleep(1)

            # cancel order
            try:
                if not bought:
                    self.binance_client.cancel_order(symbol=pair.symbol, orderId=orderId)
            except:
                pass
        if not bought:
            return None
        else:
            trade = Trade.Trade.fromNew(price, quantity, pair, self, time.time(), long_term, setup_safety_oco)
            return trade

    def handle_default(obj):
        if isinstance(obj, Trade.Trade):
            return obj.to_dict()
        elif isinstance(obj, Pair):
            return obj.to_dict()
        return None
    
    def saveCurrentSessionProfit(self):
        now = time.time()

        while self.is_saving and time.time() - now < 60:
            time.sleep(1)

        self.is_saving = True

        with open('Accounts/1/profit.txt.tmp', 'w') as f:
            f.write(str(self.realised_profit_session))

        if Path('Accounts/1/profit.txt').is_file():
            os.rename('Accounts/1/profit.txt', 'Accounts/1/profit.txt.bak')

        os.rename('Accounts/1/profit.txt.tmp', 'Accounts/1/profit.txt')

        if Path('Accounts/1/profit.txt.bak').is_file():
            os.unlink('Accounts/1/profit.txt.bak')
        self.is_saving = False
        
    def loadCurrentSessionProfit(self):
        if Path('Accounts/1/profit.txt').is_file():
            with open('Accounts/1/profit.txt', 'r') as f:
                self.realised_profit_session = float(f.read())
        

    def saveTrades(self):
        now = time.time()

        while self.is_saving and time.time() - now < 60:
            time.sleep(1)

        self.is_saving = True

        all_trades = []
        for trade in self.trades:
            all_trades.append(json.dumps(trade.__dict__, default=Account.handle_default))
        with open('Accounts/1/trades.json.tmp', 'w') as f:
            f.write(json.dumps(all_trades, sort_keys=True, indent=4))

        if Path('Accounts/1/trades.json').is_file():
            os.rename('Accounts/1/trades.json', 'Accounts/1/trades.json.bak')

        os.rename('Accounts/1/trades.json.tmp', 'Accounts/1/trades.json')

        if Path('Accounts/1/trades.json.bak').is_file():
            os.unlink('Accounts/1/trades.json.bak')

        self.is_saving = False
                
    def loadTrades(self):
        if Path('Accounts/1/trades.json').is_file():
            with open('Accounts/1/trades.json', 'r') as f:
                data = json.loads(f.read())
                for row in data:
                    self.trades.append(Trade.Trade.from_json(row, self))
                
    def updateData(self):
        data = self.binance_client.get_account()
        self.makerCommission = data['makerCommission']
        self.takerCommission = data['takerCommission']
        self.buyerCommission = data['buyerCommission']
        self.sellerCommission = data['sellerCommission']
        
        self.canTrade = data['canTrade']
        self.canWithdraw = data['canWithdraw']
        self.canDeposit = data['canDeposit']

        self.balances = {}
        for balance in data['balances']:
            self.balances[balance['asset']] = balance

    def getFreeBalance(self, symbol):
        if symbol in self.balances:
            return float(self.balances[symbol]['free'])
        else:
            return 0

    def getLockedBalance(self, symbol):
        if symbol in self.balances:
            return float(self.balances[symbol]['locked'])
        else:
            return 0

    def getTotalBalance(self, symbol):
        return self.getFreeBalance(symbol) + self.getLockedBalance(symbol)
