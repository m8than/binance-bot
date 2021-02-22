from binance.client import Client
from binance.websockets import BinanceSocketManager
from binance.depthcache import DepthCacheManager

from logging import Logger
from typing import Dict

from Pair import Pair

import time
import threading

import os
import sys

SOCKET_STREAM_LIMIT = 32

def divide_chunks(l, n): 
    for i in range(0, len(l), n):  
        yield l[i:i + n] 
  

class BInfoTicker():
    def __init__ (self, binance_client: Client, logger: Logger):
        self.binance_client = None
        self.binance_websocket_client = None
        self.work_thread = None
        self.pair_info = None
        self.logger = None
        self.socket_keys = []
        self.initiated = False

        self.binance_client = binance_client
        self.binance_websocket_client = BinanceSocketManager(self.binance_client)
        self.pair_info = {}
        self.logger = logger
        

        self.logger.info('Loading Pair Information')
        self.updatePairInfo()
        self.logger.info('Loaded Pair Information')

        self.setupWebSocket()
        self.logger.info('Binance Websockets Connected')

        time.sleep(2)
        self.logger.info('Initiating Order Books')
        self.initiatePairOrderBooks()
        self.logger.info('Initiated Order Books')

        self.logger.info('Initiating 1m Klines')
        self.initiatePair1mKlines()
        self.logger.info('Initiated 1m Klines')

        self.logger.info('Initiating 15m Klines')
        self.initiatePair15mKlines()
        self.logger.info('Initiated 15m Klines')

        self.logger.info('Initiating 1h Klines')
        self.initiatePair1hKlines()
        self.logger.info('Initiated 1h Klines')

        self.initiated = True

    def updatePairInfo(self):
        exchange_info = self.binance_client.get_exchange_info()
        usdt_symbols = [symbol for symbol in exchange_info['symbols'] if symbol['quoteAsset'] == 'USDT' and symbol['status'] == 'TRADING' and 'LEVERAGED' not in symbol['permissions']]
        # btc_symbols = [symbol for symbol in exchange_info['symbols'] if symbol['quoteAsset'] == 'BTC' and symbol['status'] == 'TRADING' and 'LEVERAGED' not in symbol['permissions']]

        # for symbol in btc_symbols:
        #     print(f'"{symbol["baseAsset"]}/{symbol["quoteAsset"]}",')

        for symbol in usdt_symbols:
            if 'USD' in symbol['baseAsset']:
                continue
            symbol_lowercase = symbol['baseAsset'].lower() + symbol['quoteAsset'].lower()
            if symbol_lowercase not in self.pair_info:
                self.pair_info[symbol_lowercase] = Pair.fromNew(symbol['baseAsset'], symbol['quoteAsset'], self.logger, self, symbol)

    def repairOrderBook(self, pair):    
        self.restartSelf()
        
        # self.logger.info(f'Repairing {pair.symbol.upper()} order book')
        # self.reconnectWebSockets()
        # pair.resetOrderBook()
        # time.sleep(5)
        # pair.initDepth(self.binance_client.get_order_book(symbol=pair.symbol, limit=1000), True)
        # self.logger.info(f'Repaired {pair.symbol.upper()} order book')

    def initiatePairOrderBooks(self):
        for symbol, pair in self.pair_info.items():
            self.logger.info(f'Initiating {symbol.upper()} order book')
            pair.initDepth(self.binance_client.get_order_book(symbol=pair.symbol, limit=1000))
            self.logger.info(f'Initiated {symbol.upper()} order book')
            time.sleep(0.33)

    def initiatePair1mKlines(self):
        for symbol, pair in self.pair_info.items():
            self.logger.info(f'Initiating {symbol.upper()} 1m klines')
            pair.initKlines1m(self.binance_client.get_klines(symbol=pair.symbol, interval='1m'))
            self.logger.info(f'Initiated {symbol.upper()} 1m klines')
            time.sleep(0.33)

    def initiatePair15mKlines(self):
        for symbol, pair in self.pair_info.items():
            self.logger.info(f'Initiating {symbol.upper()} 15m klines')
            pair.initKlines15m(self.binance_client.get_klines(symbol=pair.symbol, interval='15m'))
            self.logger.info(f'Initiated {symbol.upper()} 15m klines')
            time.sleep(0.33)

    def initiatePair1hKlines(self):
        for symbol, pair in self.pair_info.items():
            self.logger.info(f'Initiating {symbol.upper()} 1h klines')
            pair.initKlines1h(self.binance_client.get_klines(symbol=pair.symbol, interval='1h'))
            self.logger.info(f'Initiated {symbol.upper()} 1h klines')
            time.sleep(0.33)

    def restartSelf(self):
        os.execv(sys.executable,[sys.executable.split("/")[-1]]+sys.argv)
        sys.exit()


    def reconnectWebSockets(self):
        self.restartSelf()
        # for socket_key in self.socket_keys:
        #     self.binance_websocket_client.stop_socket(socket_key)
        
        # self.socket_keys.clear()
        # self.binance_websocket_client.close()
        # self.binance_websocket_client = BinanceSocketManager(self.binance_client)
        # self.setupWebSocket()

    def setupWebSocket(self):
        pair_symbols = [symbol.lower() for symbol in self.pair_info.keys()]

        stream_names = []
        for symbol in pair_symbols:
            stream_names.append(f'{symbol}@ticker')
            stream_names.append(f'{symbol}@aggTrade')
            stream_names.append(f'{symbol}@depth')
            stream_names.append(f'{symbol}@kline_1m')
            stream_names.append(f'{symbol}@kline_15m')
            stream_names.append(f'{symbol}@kline_1h')
        
        # open a websocket for every x streams
        for stream_names in divide_chunks(stream_names, SOCKET_STREAM_LIMIT):
            self.socket_keys.append(self.binance_websocket_client.start_multiplex_socket(stream_names, self.processBinanceMessage))

        self.binance_websocket_client.start()


    def processBinanceMessage(self, msg):
        if 'data' not in msg:
            self.logger.info('data missing from binance message')
            self.logger.info(msg)
            self.logger.info('Binance Websocket Issue - Reconnecting')
            self.reconnectWebSockets()
            return
        if msg['data']['e'] == 'error':
            self.logger.info('Binance Websocket Issue - Reconnecting')
            self.reconnectWebSockets()
        else:
            stream = msg['stream'].split('@')
            pair = self.pair_info[stream[0]] 
            stream_name = stream[1]

            if stream_name == 'ticker':
                pair.processTickerStream(msg['data'])
            elif stream_name == 'aggTrade':
                pair.processAggregatedTrade(msg['data'])
            elif stream_name == 'depth':
                pair.processUpdateDepth(msg['data'])
            elif stream_name == 'kline_1m':
                pair.processKline1m(msg['data'])
            elif stream_name == 'kline_15m':
                pair.processKline15m(msg['data'])
            elif stream_name == 'kline_1h':
                pair.processKline1h(msg['data'])
            else:
                self.logger.info('Unsupported message from binance stream: {}, data: {}'.format(msg['stream'], msg['data']))