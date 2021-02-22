import json
import time

from binance.enums import ORDER_RESP_TYPE_FULL, ORDER_TYPE_STOP_LOSS, ORDER_TYPE_STOP_LOSS_LIMIT, SIDE_BUY, SIDE_SELL, TIME_IN_FORCE_GTC
from Pair import Pair
import copy
import Account
from humanfriendly import format_timespan
from binance.enums import *

def truncate_float(n, places):
    return int(n * (10 ** places)) / 10 ** places

class Trade():
    def __init__(self, data):
        self.__dict__.update(data)

    @classmethod
    def fromNew(cls, price, quantity, pair : Pair, account, buy_time, long_term, setup_safety_oco = True):
        attr = {}
        attr['symbol'] = pair.symbol
        attr['price'] = price
        attr['quantity'] = quantity
        attr['long_term'] = long_term
        attr['buy_time'] = buy_time
        attr['account'] = account
        attr['buy_pair'] = copy.copy(pair)
        attr['current_order_id'] = None
        attr['va_count'] = 1
        attr['initial_buy'] = float(price) * float(quantity)

        attr['last_trailing_stop_price'] = 0

        attr['last_check_1d'] = buy_time
        attr['last_check_30s'] = buy_time
        attr['last_check_2s'] = buy_time
        trade = cls(attr)
        if setup_safety_oco:
            if long_term:
                trade.setupSafetyNetOCO()
            else:
                trade.setupSafetyNetOCO(upper_ratio=1.1,stop_ratio=0.9)

        return trade

    def getPair(self):
        return self.account.binfoticker.pair_info[self.symbol.lower()]

    def getCurrentValue(self):
        return float(self.quantity) * float(self.getPair().last_price)

    def getInvestmentValue(self):
        return float(self.quantity) * float(self.price)

    def setupSellOrder(self):
        if self.current_order_id != None:
            try:
                self.account.binance_client.cancel_order(symbol = self.symbol, orderId = self.current_order_id)
                self.current_order_id = None
            except:
                pass

        try:
            order = self.account.binance_client.order_market_sell(
                symbol=self.symbol,
                quantity=self.quantity
                )
            self.current_order_id = order['orderId']
        except Exception as e:
            print(e)
            pass

    def setupTrailingStop(self, base_price, stop_ratio = 0.01):
        stop_price = round(base_price * (1 - stop_ratio), self.getPair().price_precision)
        limit_price = truncate_float(stop_price * 0.999999999, self.getPair().price_precision)
        
        if self.last_trailing_stop_price > stop_price:
            return


        if self.current_order_id != None:
            try:
                self.account.binance_client.cancel_order(symbol = self.symbol, orderId = self.current_order_id)
                self.current_order_id = None
            except:
                pass

        try:
            order = self.account.binance_client.create_order(
                symbol = self.symbol,
                quantity = float(self.quantity),
                price = limit_price,
                stopPrice = stop_price,
                side = SIDE_SELL,
                type = ORDER_TYPE_STOP_LOSS_LIMIT,
                timeInForce = TIME_IN_FORCE_GTC,
                newOrderRespType = ORDER_RESP_TYPE_FULL
                )
            self.last_trailing_stop_price = stop_price
            self.current_order_id = order['orderId']
        except:
            self.last_trailing_stop_price = 0

    def setupTrailingOCO(self, base_price = None):
        
        if self.current_order_id != None:
            self.account.binance_client.cancel_order(symbol = self.symbol, orderId = self.current_order_id)
            self.current_order_id = None

        ## setup flat 5% 5% - to be updated later ##

        if base_price == None:
            base_price = float(self.price)

        upper_price = round(float(self.price) * 1.15, self.getPair().price_precision)
        lower_price = round(base_price * 0.95, self.getPair().price_precision)
        stop_price = round(lower_price * 1.02, self.getPair().price_precision)

        order = self.account.binance_client.order_oco_sell(
            symbol = self.symbol,
            quantity = float(self.quantity),
            price = upper_price,
            stopPrice = stop_price,
            stopLimitPrice = lower_price,
            stopLimitTimeInForce = TIME_IN_FORCE_GTC,
            newOrderRespType = ORDER_RESP_TYPE_FULL,
            )


        self.current_order_id = order['orders'][0]['orderId']

    def setupSafetyNetOCO(self, base_price = None, upper_ratio = 1.15, stop_ratio = 0.73):
        
        if self.current_order_id != None:
            try:
                self.account.binance_client.cancel_order(symbol = self.symbol, orderId = self.current_order_id)
            except:
                pass
            self.current_order_id = None

        if base_price == None:
            base_price = float(self.price)

        upper_price = round(base_price * upper_ratio, self.getPair().price_precision)
        stop_price = round(base_price * stop_ratio, self.getPair().price_precision)
        lower_price = truncate_float(stop_price * 0.999999999, self.getPair().price_precision)

        order = self.account.binance_client.order_oco_sell(
            symbol = self.symbol,
            quantity = float(self.quantity),
            price = upper_price,
            stopPrice = stop_price,
            stopLimitPrice = lower_price,
            stopLimitTimeInForce = TIME_IN_FORCE_GTC,
            newOrderRespType = ORDER_RESP_TYPE_FULL,
            )


        self.current_order_id = order['orders'][0]['orderId']

    def ticker(self):
        now = time.time()
        seconds_since_last_check_1d = now - self.last_check_1d
        seconds_since_last_check_30s = now - self.last_check_30s
        seconds_since_last_check_2s = now - self.last_check_2s
        age = now - self.buy_time
        self.account : Account.Account

        if age > 60*60*48:
            self.long_term = True            

        if seconds_since_last_check_2s > 1:
            self.last_check_2s = now

            if float(self.account.getTotalBalance(self.buy_pair.base_asset)) != float(self.quantity):
                self.account.deleteTrade(self.symbol)
                realised_profit = (float(self.getCurrentValue()) - float(self.getInvestmentValue()))
                realised_profit_percentage = realised_profit / self.getInvestmentValue() * 100
                self.account.realised_profit_session += realised_profit
                self.account.saveCurrentSessionProfit()
                accuracy_short, investment_short, pattern_short, distance_short, order_book_rating_short = self.buy_pair.getShortTermRating()
                accuracy_long, investment_long, pattern_long, distance_long, order_book_rating_long = self.buy_pair.getLongTermRating()
                current_accuracy_short, current_investment_short, current_pattern_short, current_distance_short, current_order_book_rating_short = self.getPair().getShortTermRating()
                current_accuracy_long, current_investment_long, current_pattern_long, current_distance_long, current_order_book_rating_long = self.getPair().getLongTermRating()
                self.account.logger.info(f'Trade Finished - {self.symbol} [trade length: {format_timespan(age)}]')
                self.account.logger.info(f' [profit made: {realised_profit_percentage}%]')
                self.account.logger.info(f' [original short rating: {investment_short}%]')
                self.account.logger.info(f' [original long rating: {investment_long}%]')
                self.account.logger.info(f' [current short rating: {current_investment_short}%]')
                self.account.logger.info(f' [current long rating: {current_investment_long}%]')
                self.account.logger.info(f' [long term?: {self.long_term}]')
                return

            if self.getPair().sellSignal(self.long_term):
                if self.getCurrentValue() > self.getInvestmentValue() * 1.01:
                    self.account.logger.info(f'[SELL SIGNAL ({self.symbol})]')
                    self.setupSellOrder()
                    return

            if self.long_term == False and self.getPair().last_price > self.price * 1.02:
                if self.last_trailing_stop_price == 0 or self.last_trailing_stop_price < self.getPair().last_price * 0.98:
                    self.setupTrailingStop(self.getPair().last_price, 0.015)
            if self.long_term == True and self.getPair().last_price > self.price * 1.12:
                if self.last_trailing_stop_price == 0 or self.last_trailing_stop_price < self.getPair().last_price * 0.97:
                    self.setupTrailingStop(self.getPair().last_price, 0.025)

            #elif self.getPair().last_price > self.price * 1.01:
                #self.setupTrailingOCO(self.getPair().last_price)

        if seconds_since_last_check_30s > 30:
            self.last_check_30s = now

        if seconds_since_last_check_1d > 60*60*24 and self.long_term:
            #VA :)            

            target_value = float(self.initial_buy) * (self.va_count + 1)
            current_value = float(self.getPair().last_price) * float(self.quantity)

            new_buy = target_value - current_value

            if new_buy < 10:
                new_buy = 10

            if new_buy < self.account.getFreeBalance('USDT'):

                old_accuracy_long, old_investment_long, old_pattern_long, old_distance_long, old_order_book_rating_long = self.buy_pair.getLongTermRating()
                accuracy_long, investment_long, pattern_long, distance_long, order_book_rating_long = self.getPair().getLongTermRating()
                
                if accuracy_long > 0.5 and (investment_long - old_investment_long) > -0.1 and self.va_count < 5:
                    trade = self.account.buy(self.getPair(), new_buy, True, False)

                    total_cost = float(self.price) * float(self.quantity)
                    total_cost += float(trade.price) * float(trade.quantity)

                    
                    self.quantity = float(self.quantity) + float(trade.quantity)

                    self.account.logger.info(f'({self.buy_pair.symbol}) activating VA (buy count: {self.va_count})')
                    self.account.logger.info(f'[Old Price ({self.price})]')
                    self.price = round(total_cost / float(self.quantity), 4)
                    self.account.logger.info(f'[New Price ({self.price})]')
                    self.va_count += 1
                    self.setupSafetyNetOCO(upper_ratio=1.15, stop_ratio=0.85)
                    
                    self.last_check_1d = now

    
    def to_dict(self):
        obj = copy.copy(self)
        del obj.account
        return obj.__dict__

    @classmethod
    def from_json(cls, data, account):
        row = json.loads(data)
        row['buy_pair'] = Pair(row['buy_pair'])
        row['buy_pair'].logger = account.logger
        row['buy_pair'].binfoticker = account.binfoticker
        row['account'] = account
        return cls(row)
