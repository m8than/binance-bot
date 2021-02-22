import threading
from Trade import Trade
import pickle
from Account import Account
from PatternDetection import PatternDetection, PatternTypes
from Pair import Pair
from BInfoTicker import BInfoTicker
from binance.client import Client
from binance.websockets import BinanceSocketManager
import time
from pathlib import Path

class BBot:

    def __init__ (self, api_key, api_secret, logger):
        self.binance_client = Client(api_key, api_secret)
        self.binfo_ticker = BInfoTicker(self.binance_client, logger)
        self.logger = logger
        self.current_trades = []

        self.account = Account(self.binance_client, self.binfo_ticker, logger)
        self.account.loadTrades()
        
        pass #do stuff

    def runTradeTickers(self):
        time.sleep(2)
        while True:
            trade : Trade
            self.account.updateData()
            for trade in self.account.trades:
                try:
                    trade.ticker()
                except Exception as e:
                    self.logger.info(e)
                    pass
                
            self.account.saveTrades()
            #self.logger.info(f'[Investment Value: {investment_value}] [Current Value: {current_value}]')
            time.sleep(0.66)

    def run(self):
        while not self.binfo_ticker.initiated:
            time.sleep(1)

        tradeTickerThread = threading.Thread(target=self.runTradeTickers, name="Trade Ticker")
        tradeTickerThread.start()

        while True:
            investment_value = 0
            current_value = 0
            for trade in self.account.trades:
                investment_value += trade.getInvestmentValue()
                current_value += trade.getCurrentValue()
            unrealised_profit = (current_value-investment_value)
            self.logger.info(f'[Investment Value: {investment_value:.3f}] [Current Value: {current_value:.3f}] [Unrealised Profit: {unrealised_profit:.3f}] [Current Session Profit: {self.account.realised_profit_session:.3f}] [Current Trades: {len(self.account.trades)}]')
            #self.logger.info('Updating account information')
            self.account.updateData()

            self.logger.info('Searching for good trades...')            
            pair: Pair
            for symbol, pair in self.binfo_ticker.pair_info.items():


                # self.logger.info(f'({symbol.upper()}) 15m candlestick pattern detected: {pattern_15m.name}'
                #                 f' (distance: {distance_15m*15} minutes)'
                #                 f' (type: {type_15m})')

                # self.logger.info(f'({symbol.upper()}) 1m candlestick pattern detected: {pattern_1m.name}'
                #                 f' (distance: {distance_1m} minutes)'
                #                 f' (type: {type_1m})')

                accuracy_short, investment_short, pattern_short, distance_short, order_book_rating_short = pair.getShortTermRating()
                accuracy_long, investment_long, pattern_long, distance_long, order_book_rating_long = pair.getLongTermRating()

                #self.logger.info(f'({symbol.upper()}) 1m candlestick pattern detected: {pattern_short.name}'
                #                f' (distance: {distance_short} minutes)')

                #self.logger.info(f'({symbol.upper()}) 1h candlestick pattern detected: {pattern_long.name}'
                #                f' (distance: {distance_long*15} minutes)')

                #self.logger.info(f'({symbol.upper()}) [short term: {investment_short}]  [long term: {investment_long}]')

                if investment_short < 0.55 or investment_long < 0.6:
                    continue

                if accuracy_short > 0.7 and investment_short > 0.75:
                    self.account.updateData()
                    # if not already trading
                    if not self.account.tradeExists(symbol):
                        # if enough free balance and not already manually trading
                        if self.account.getFreeBalance('USDT') > 25 and self.account.getTotalBalance(pair.base_asset) == 0:
                            self.logger.info(f'({symbol.upper()}) attempting to buy $25 worth (short term)')
                            self.logger.info(f'short term: (accuracy: {accuracy_short}) (investment: {investment_short}) (pattern: {pattern_short.name}) (distance: {distance_short}m) (order rating: {order_book_rating_short})')
                            trade = self.account.buy(pair, 25, False)
                            self.account.trades.append(trade)
                            self.account.saveTrades()
                            if trade == None:
                                self.logger.info('order failed')
                            else:
                                self.logger.info('order fullfilled')
                                self.account.updateData()
                                continue

                if accuracy_long > 0.8 and investment_long > 0.75:
                    self.account.updateData()
                    # if not already trading
                    if not self.account.tradeExists(symbol):
                        # if enough free balance and not already manually trading
                        if self.account.getFreeBalance('USDT') > 20 and self.account.getTotalBalance(pair.base_asset) == 0:
                            self.logger.info(f'({symbol.upper()}) attempting to buy $20 worth (long term)')
                            self.logger.info(f'long term: (accuracy: {accuracy_long}) (investment: {investment_long}) (pattern: {pattern_long.name}) (distance: {distance_long}m) (order rating: {order_book_rating_long})')
                            trade = self.account.buy(pair, 20, True)
                            self.account.trades.append(trade)
                            self.account.saveTrades()
                            if trade == None:
                                self.logger.info('order failed')
                            else:
                                self.logger.info('order fullfilled')
                                self.account.updateData()
                                continue

                

                # if accuracy_short > 0.6 and accuracy_long > 0.5:
                #     if investment_short > 0.55 and investment_long > 0.45 and (investment_short + investment_long) > 1.1:
                #         self.account.updateData()
                #         if not self.account.tradeExists(symbol):
                #             if self.account.getFreeBalance('USDT') > 15 and self.account.getFreeBalance(pair.base_asset) == 0:
                #                 #self.logger.info(f'short term: (accuracy: {accuracy_short}) (investment: {investment_short}) (pattern: {pattern_short.name}) (distance: {distance_short}m) (order rating: {order_book_rating_short})')
                #                 #self.logger.info(f'long term: (accuracy: {accuracy_long}) (investment: {investment_long}) (pattern: {pattern_long.name}) (distance: {distance_long}h) (order rating: {order_book_rating_long})')
                #                 self.logger.info(f'({symbol.upper()}) attempting to buy $15 worth')
                #                 trade = self.account.buy(pair, 15)
                #                 self.account.trades.append(trade)
                #                 self.account.saveTrades()

                #                 if trade == None:
                #                     self.logger.info('------ order failed')
                #                 else:
                #                     self.logger.info('------ order fullfilled')
                #                     self.account.updateData()

            time.sleep(5)
