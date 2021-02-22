import copy
import time
from PatternDetection import PatternDetection, PatternTypes
from binance.enums import *
import numpy
import talib
import pandas as pd


TRADE_HISTORY_MAX_LENGTH = 1000
KLINE_1M_HISTORY_MAX_LENGTH = 1024 #minutely
KLINE_15M_HISTORY_MAX_LENGTH = 1024 #15 minutely
KLINE_1H_HISTORY_MAX_LENGTH = 1024 #hourly

class Pair:
    def __init__(self, data):
        self.__dict__.update(data)

    @classmethod
    def fromNew(cls, base_asset, quote_asset, logger, binfoticker, data):
        attr = {}
        for symbol_filter in data['filters']:
            if symbol_filter['filterType'] == 'PRICE_FILTER':
                tickSize = symbol_filter['tickSize'].rstrip('0')
                attr['price_precision'] = int(tickSize[::-1].find('.'))
            if symbol_filter['filterType'] == 'LOT_SIZE':
                stepSize = symbol_filter['stepSize'].rstrip('0')
                attr['quantity_precision'] = int(stepSize[::-1].find('.'))

        attr['last_price'] = None

        attr['best_bid_price'] = None
        attr['best_bid_quantity'] = None

        attr['best_ask_price'] = None
        attr['best_ask_quantity'] = None

        # daily means over the last 24 hours not just today lol xd 

        attr['daily_open'] = None
        attr['daily_high'] = None
        attr['daily_low'] = None

        attr['daily_base_asset_volume'] = None
        attr['daily_quote_asset_volume'] = None

        attr['daily_trade_count'] = None

        attr['base_asset'] = base_asset
        attr['quote_asset'] = quote_asset
        attr['symbol'] = base_asset + quote_asset

        attr['aggregated_trade_history'] = []


        attr['klines_1m'] = []
        attr['klines_15m'] = []
        attr['klines_1h'] = []

        attr['logger'] = logger
        attr['binfoticker'] = binfoticker

        pair = cls(attr)
        pair.resetOrderBook()
        return pair


    def isBearish():
        #get it
        pass

    def initDepth(self, data, repair = False):
        data = data.copy()

        for i in range(len(data['bids'])):
            data['bids'][i][0] = float(data['bids'][i][0])
            data['bids'][i][1] = float(data['bids'][i][1])

        for i in range(len(data['asks'])):
            data['asks'][i][0] = float(data['asks'][i][0])
            data['asks'][i][1] = float(data['asks'][i][1])


        self.order_book = data

        if repair:
            time.sleep(3.3)

        self.order_book_buffer_events = False
        while len(self.order_book_buffer) > 0:
            self.updateDepth(self.order_book_buffer.pop(0))
            
    
    def klines1hReady(self):
        return len(self.klines_1h) > 0

    def klines15mReady(self):
        return len(self.klines_15m) > 0

    def klines1mReady(self):
        return len(self.klines_1m) > 0

    def resetOrderBook(self):
        self.order_book_buffer_events = True
        
        self.order_book_initiated = False
        self.order_book_first_update_done = False
        
        self.order_book = {}
        self.order_book_buffer = []


    def processUpdateDepth(self, data):
        if self.order_book_buffer_events:
            self.order_book_buffer.append(data)
            return
            
        # drop if update outdated
        if data['u'] <= self.order_book['lastUpdateId']:
            return
            
        if not self.order_book_first_update_done:
            if not (data['U'] <= self.order_book['lastUpdateId']+1 and data['u'] >= self.order_book['lastUpdateId']+1):
                self.logger.info(f'({self.symbol}) fatal order book error')
                self.binfoticker.repairOrderBook(self)
                return
        else:
            self.order_book_first_update_done = True

        
        if data['U'] != self.order_book['lastUpdateId'] + 1:
            self.logger.info(f'({self.symbol}) order book mismatch')
            return


        self.updateDepth(data)

    def updateDepth(self, data):
        self.order_book['lastUpdateId'] = data['u']

        try:
            for bid in data['b']:
                level = float(bid[0])
                absolute_quantity = float(bid[1])

                for i in range(len(self.order_book['bids'])):
                    order = self.order_book['bids'][i]
                    if order[0] == level:
                        if absolute_quantity > 0:
                            order[1] = absolute_quantity
                        else:
                            del self.order_book['bids'][i]
                        break
                    elif order[0] > level:
                        # if higher level and not broken yet
                        if absolute_quantity > 0:
                            self.order_book['bids'].insert(i, [level, absolute_quantity])
                        break


            for ask in data['a']:
                level = float(ask[0])
                absolute_quantity = float(ask[1])

                for i in range(len(self.order_book['asks'])):
                    order = self.order_book['asks'][i]
                    if order[0] == level:
                        if absolute_quantity > 0:
                            order[1] = absolute_quantity
                        else:
                            del self.order_book['asks'][i]
                        break
                    elif order[0] > level:
                        # if higher level and not broken yet
                        if absolute_quantity > 0:
                            self.order_book['asks'].insert(i, [level, absolute_quantity])
                        break
        except:
            pass



    def processAggregatedTrade(self, data):
        trade_data = {
            'trade_id': data['a'],
            'price': float(data['p']),
            'quantity': float(data['q']),
            'event_time': data['E'],
            'trade_time': data['T'],
            'first_trade_id': data['f'],
            'last_trade_id': data['l'],
            'trade_time': data['T'],
            'market_maker': data['m'],
            'total_value': float(data['p']) * float(data['q'])
        }

        self.aggregated_trade_history.append(trade_data)
        
        # remove first from list if over max length
        if len(self.aggregated_trade_history) > TRADE_HISTORY_MAX_LENGTH:
            self.aggregated_trade_history.pop(0)


    def processTickerStream(self, data):
        self.last_price = float(data['c'])

        self.best_bid_price = float(data['b'])
        self.best_bid_quantity = float(data['B'])

        self.best_ask_price = float(data['a'])
        self.best_ask_quantity = float(data['A'])

        self.daily_open = float(data['o'])
        self.daily_high = float(data['h'])
        self.daily_low = float(data['l'])

        self.daily_base_asset_volume = float(data['v'])
        self.daily_quote_asset_volume = float(data['q'])

        self.daily_trade_count = float(data['n'])

    def processKline1m(self, data):
        if not self.klines1mReady():
            return

        data = data['k']
        parsed = {
            'open_time': float(data['t']),
            'open_price': float(data['o']),
            'high_price': float(data['h']),
            'low_price': float(data['l']),
            'close_price': float(data['c']),
            'base_asset_volume': float(data['v']),
            'close_time': data['T'],
            'quote_asset_volume': float(data['q']),
            'trade_count': data['n'],
            'taker_buy_base_asset_volume': float(data['V']),
            'taker_buy_quote_asset_volume': float(data['Q']),
            'closed': data['x']
        }

        if len(self.klines_1m) > 1 and self.klines_1m[-1]['open_time'] == parsed['open_time'] and self.klines_1m[-1]['close_time'] == parsed['close_time']:
            self.klines_1m[-1] = parsed
        else:
            self.klines_1m.append(parsed)
        
        if len(self.klines_1m) > KLINE_1M_HISTORY_MAX_LENGTH:
            self.klines.pop(0)
        return

    def processKline15m(self, data):
        if not self.klines15mReady():
            return

        data = data['k']

        parsed = {
            'open_time': float(data['t']),
            'open_price': float(data['o']),
            'high_price': float(data['h']),
            'low_price': float(data['l']),
            'close_price': float(data['c']),
            'base_asset_volume': float(data['v']),
            'close_time': data['T'],
            'quote_asset_volume': float(data['q']),
            'trade_count': data['n'],
            'taker_buy_base_asset_volume': float(data['V']),
            'taker_buy_quote_asset_volume': float(data['Q']),
            'closed': data['x']
        }

        if len(self.klines_15m) > 1 and self.klines_15m[-1]['open_time'] == parsed['open_time'] and self.klines_15m[-1]['close_time'] == parsed['close_time']:
            self.klines_15m[-1] = parsed
        else:
            self.klines_15m.append(parsed)
        
        if len(self.klines_15m) > KLINE_15M_HISTORY_MAX_LENGTH:
            self.klines.pop(0)
        return

    def processKline1h(self, data):
        if not self.klines1hReady():
            return

        data = data['k']

        parsed = {
            'open_time': float(data['t']),
            'open_price': float(data['o']),
            'high_price': float(data['h']),
            'low_price': float(data['l']),
            'close_price': float(data['c']),
            'base_asset_volume': float(data['v']),
            'close_time': data['T'],
            'quote_asset_volume': float(data['q']),
            'trade_count': data['n'],
            'taker_buy_base_asset_volume': float(data['V']),
            'taker_buy_quote_asset_volume': float(data['Q']),
            'closed': data['x']
        }

        if len(self.klines_1h) > 1 and self.klines_1h[-1]['open_time'] == parsed['open_time'] and self.klines_1h[-1]['close_time'] == parsed['close_time']:
            self.klines_1h[-1] = parsed
        else:
            self.klines_1h.append(parsed)
        
        if len(self.klines_1h) > KLINE_1H_HISTORY_MAX_LENGTH:
            self.klines.pop(0)
        return

    def initKlines1h(self, data):
        for kline in data:
            self.klines_1h.append({
                'open_time': float(kline[0]),
                'open_price': float(kline[1]),
                'high_price': float(kline[2]),
                'low_price': float(kline[3]),
                'close_price': float(kline[4]),
                'base_asset_volume': float(kline[5]),
                'close_time': kline[6],
                'quote_asset_volume': float(kline[7]),
                'trade_count': kline[8],
                'taker_buy_base_asset_volume': float(kline[9]),
                'taker_buy_quote_asset_volume': float(kline[10]),
                'closed': True
            })


    def initKlines15m(self, data):
        for kline in data:
            self.klines_15m.append({
                'open_time': float(kline[0]),
                'open_price': float(kline[1]),
                'high_price': float(kline[2]),
                'low_price': float(kline[3]),
                'close_price': float(kline[4]),
                'base_asset_volume': float(kline[5]),
                'close_time': kline[6],
                'quote_asset_volume': float(kline[7]),
                'trade_count': kline[8],
                'taker_buy_base_asset_volume': float(kline[9]),
                'taker_buy_quote_asset_volume': float(kline[10]),
                'closed': True
            })

    def initKlines1m(self, data):
        for kline in data:
            self.klines_1m.append({
                'open_time': float(kline[0]),
                'open_price': float(kline[1]),
                'high_price': float(kline[2]),
                'low_price': float(kline[3]),
                'close_price': float(kline[4]),
                'base_asset_volume': float(kline[5]),
                'close_time': kline[6],
                'quote_asset_volume': float(kline[7]),
                'trade_count': kline[8],
                'taker_buy_base_asset_volume': float(kline[9]),
                'taker_buy_quote_asset_volume': float(kline[10]),
                'closed': True
            })

    bullish = [
        PatternTypes.INVERSE_HEAD_AND_SHOULDERS,
        PatternTypes.FALLING_WEDGE,
        PatternTypes.DOUBLE_BOTTOM,
        PatternTypes.ASCENDING_TRIANGLE
    ]

    bearish = [
        PatternTypes.HEAD_AND_SHOULDERS,
        PatternTypes.RISING_WEDGE,
        PatternTypes.DOUBLE_TOP,
        PatternTypes.DESCENDING_TRIANGLE
    ]

    def getShortTermRating(self):
        accuracy_rating = []
        investment_rating = []

        ## Start Pattern Checking ##
        pattern_1m, distance_1m = PatternDetection.detectPattern(self.klines_1m)
        pattern_15m, distance_15m = PatternDetection.detectPattern(self.klines_15m)

        investment_rating.append(0 if pattern_1m in self.bearish else 1 if pattern_1m in self.bullish else 0.5)
        investment_rating.append(0 if pattern_15m in self.bearish else 1 if pattern_15m in self.bullish else 0.5)

        if distance_15m <= 16 and distance_1m <= 20:
            accuracy_rating.append(((20 - max(0, distance_1m-10))/20))
            accuracy_rating.append(((12 - max(0, distance_15m-8)))/12)
        else:
            accuracy_rating.append(0)
            accuracy_rating.append(0)
        ## End Pattern Checking ##

        ## Start Order Book Checking ##
        shortTermAskVolume = self.getAskVolumeWithinPercentage(0.02)
        shortTermBidVolume = self.getBidVolumeWithinPercentage(0.02)
        shortTermTotalVolume = shortTermAskVolume + shortTermBidVolume

        order_book_rating = 0
        if shortTermTotalVolume != 0:
            accuracy_rating.append(1)
            investment_rating.append(shortTermAskVolume/shortTermTotalVolume)
            order_book_rating = shortTermAskVolume/shortTermTotalVolume
        ## End Order Book Checking ##

        ## RSI checking ##
        rsi_1m = self.getRSI(self.klines_1m, 10)
        rsi_15m = self.getRSI(self.klines_15m, 6)

        investment_rating.append(1 - (rsi_1m[-1] / 100))
        investment_rating.append(1 - (rsi_15m[-1] / 100))
        accuracy_rating.append(1)
        accuracy_rating.append(1)
        ## RSI checking ##

        ## StochRSI checking ##
        slowk_1m, slowd_1m = self.getStochRsi(rsi_1m, 3, 3, 14)
        stochrsi_analysis_1m = self.stochRsiAnalysis(slowk_1m, slowd_1m, 3)

        investment_rating.append(stochrsi_analysis_1m)
        accuracy_rating.append(1)

        slowk_15m, slowd_15m = self.getStochRsi(rsi_15m, 3, 3, 14)
        stochrsi_analysis_15m = self.stochRsiAnalysis(slowk_15m, slowd_15m, 3)

        investment_rating.append(stochrsi_analysis_15m)
        accuracy_rating.append(1)
        ## StochRSI checking ##

        ## ADXR checking ##
        adx_1m = self.getADX(self.klines_1m, 5)
        adxr_1m = self.getADXR(self.klines_1m, 5)
        adxr_1m_analysis = self.adxAdxrAnalysis(adx_1m, adxr_1m, 6)
        investment_rating.append(adxr_1m_analysis)
        accuracy_rating.append(1)

        adx_15m = self.getADX(self.klines_15m, 5)
        adxr_15m = self.getADXR(self.klines_15m, 5)
        adxr_15m_analysis = self.adxAdxrAnalysis(adx_15m, adxr_15m, 3)
        investment_rating.append(adxr_15m_analysis)
        accuracy_rating.append(1)
        ## ADXR checking ##
                
        accuracy = round(sum(accuracy_rating) / len(accuracy_rating), 2)
        investment = round(sum(investment_rating) / len(investment_rating), 2)

        return (accuracy, investment, pattern_1m, distance_1m, order_book_rating)

    def adxAdxrAnalysis(self, adx, adxr, lookback):
        adx_recent = adx[-lookback:]
        adxr_recent = adxr[-lookback:]

        investment_rating = 0.5

        if adxr_recent[-1] > 25: 
            if adx_recent[0] < adxr_recent[0]:
                if adx_recent[-1] > adxr_recent[-1]:
                    investment_rating = 1

        if adxr_recent[-1] > 25: 
            if adx_recent[0] > adxr_recent[0]:
                if adx_recent[-1] < adxr_recent[-1]:
                    investment_rating = 0

        return investment_rating

    def stochRsiAnalysis(self, slowk, slowd, lookback):
        slowk_recent = slowk[-lookback:]
        slowd_recent = slowd[-lookback:]

        investment_rating = 0.5

        if slowk_recent.iloc[-1][0] < 20: 
            if slowk_recent.iloc[0][0] < slowd_recent.iloc[0][0]:
                if slowk_recent.iloc[-1][0] > slowd_recent.iloc[-1][0]:
                    investment_rating = 1

        if slowk_recent.iloc[-1][0] > 80: 
            if slowk_recent.iloc[0][0] > slowd_recent.iloc[0][0]:
                if slowk_recent.iloc[-1][0] < slowd_recent.iloc[-1][0]:
                    investment_rating = 0

        return investment_rating

    def getStochRsi(self, rsi, smoothK, smoothD, period):
        rsi_dataframe = pd.DataFrame(rsi)
        stochrsi  = (rsi_dataframe - rsi_dataframe.rolling(period).min()) / (rsi_dataframe.rolling(period).max() - rsi_dataframe.rolling(period).min())
        slowk = stochrsi.rolling(smoothK).mean() * 100
        slowd = slowk.rolling(smoothD).mean()

        return slowk, slowd


    def getKlineColumn(self, klines, column='close_price', count=99999999999):
        return numpy.array([kline[column] for kline in klines[-count:]])

    def getADX(self, klines, timeperiod):
        close = self.getKlineColumn(klines, 'close_price')
        high = self.getKlineColumn(klines, 'high_price')
        low = self.getKlineColumn(klines, 'low_price')
        return talib.ADX(high, low, close, timeperiod=timeperiod)

    def getADXR(self, klines, timeperiod):
        close = self.getKlineColumn(klines, 'close_price')
        high = self.getKlineColumn(klines, 'high_price')
        low = self.getKlineColumn(klines, 'low_price')
        return talib.ADXR(high, low, close, timeperiod=timeperiod)


    def getRSI(self, klines, timeperiod):
        close_prices = self.getKlineColumn(klines, 'close_price')
        return talib.RSI(close_prices, timeperiod=timeperiod)

    def sellSignal(self, long_term):
        
        ## RSI checking ##
        if long_term:
            rsi = self.getRSI(self.klines_1h, 14)
        else:
            rsi = self.getRSI(self.klines_15m, 14)
        ## RSI checking ##

        ## StochRSI checking ##
        slowk, slowd = self.getStochRsi(rsi, 3, 3, 14)
        stochrsi_analysis = self.stochRsiAnalysis(slowk, slowd, 3)
        ## StochRSI checking ##

        ## Order checking ##
        if long_term:
            askVolume = self.getAskVolumeWithinPercentage(0.1)
            bidVolume = self.getBidVolumeWithinPercentage(0.1)
        else:
            askVolume = self.getAskVolumeWithinPercentage(0.05)
            bidVolume = self.getBidVolumeWithinPercentage(0.05)

        totalVolume = askVolume + bidVolume

        order_book_rating = 0
        if totalVolume != 0:
            order_book_rating = askVolume/totalVolume
        ## Order checking ##

        return stochrsi_analysis == 0 and order_book_rating < 0.5

    def getLongTermRating(self):
        accuracy_rating = []
        investment_rating = []

        ## Start Pattern Checking ##
        pattern_1h, distance_1h = PatternDetection.detectPattern(self.klines_1h)

        investment_rating.append(0 if pattern_1h in self.bearish else 1 if pattern_1h in self.bullish else 0.5)

        if distance_1h <= 24:
            accuracy_rating.append(((24 - max(0, distance_1h-5)))/24)
        else:
            accuracy_rating.append(0)
        ## End Pattern Checking ##

        ## RSI checking ##
        rsi_1h = self.getRSI(self.klines_1h, 14)
        investment_rating.append(1 - (rsi_1h[-1] / 100))
        accuracy_rating.append(1)
        ## RSI checking ##

        ## StochRSI checking ##
        slowk, slowd = self.getStochRsi(rsi_1h, 3, 3, 14)
        stochrsi_analysis = self.stochRsiAnalysis(slowk, slowd, 3)

        investment_rating.append(stochrsi_analysis)
        accuracy_rating.append(1)
        ## StochRSI checking ##


        ## ADXR checking ##
        adx_1h = self.getADX(self.klines_1h, 10)
        adxr_1h = self.getADXR(self.klines_1h, 10)
        adxr_1h_analysis = self.adxAdxrAnalysis(adx_1h, adxr_1h, 3)
        investment_rating.append(adxr_1h_analysis)
        accuracy_rating.append(1)
        ## ADXR checking ##

        ## Start Order Book Checking ##
        longTermAskVolume = self.getAskVolumeWithinPercentage(0.5)
        longTermBidVolume = self.getBidVolumeWithinPercentage(0.5)

        longTermTotalVolume = longTermAskVolume + longTermBidVolume

        order_book_rating = 0
        if longTermTotalVolume != 0:
            accuracy_rating.append(1)
            investment_rating.append(longTermAskVolume/longTermTotalVolume)
            order_book_rating = longTermAskVolume/longTermTotalVolume
        ## End Order Book Checking ##
            
        accuracy = round(sum(accuracy_rating) / len(accuracy_rating), 2)
        investment = round(sum(investment_rating) / len(investment_rating), 2)

        ## TODO: add aroon

        return (accuracy, investment, pattern_1h, distance_1h, order_book_rating)


    def getAskVolumeWithinPercentage(self, percentage):
        if 'lastUpdateId' not in self.order_book:
            return 0

        if self.last_price == None:
            return 0

        upper_threshold = self.last_price * (1+percentage)
        asks = self.order_book['asks']
        total = 0

        for ask in asks:
            if float(ask[0]) < upper_threshold:
                total += float(ask[1])

        return total * self.last_price


    def getBidVolumeWithinPercentage(self, percentage):
        if 'lastUpdateId' not in self.order_book:
            return 0
            
        if self.last_price == None:
            return 0

        lower_threshold = self.last_price * (1-percentage)
        bids = self.order_book['bids']
        total = 0

        for bid in bids:
            if float(bid[0]) > lower_threshold:
                total += float(bid[1])

        return total * self.last_price
        
    def to_dict(self):
        obj = copy.copy(self)
        del obj.binfoticker
        del obj.logger
        return obj.__dict__