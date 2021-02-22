from binance.client import Client
from BBot import BBot
import logging
import sys


api_key = "6afXLcczBgllOAKlQ71K61qckRarFUXExWK5KJEZwNlTeBDc6YF3GsjpxNLNYqrn"
api_secret = "BAL1o5tV1qDpVlk62ocEOtQxcEIqFzxOlwFxlz1b61jP3qpSNDcnGl5iqilMSDt4"

def main():
    logFormat = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

    logger = logging.getLogger('BBot')
    logger.setLevel(logging.DEBUG)

    logFileHandler = logging.FileHandler('debug.log')
    logFileHandler.setFormatter(logFormat)
    logger.addHandler(logFileHandler)

    logConsoleHandler = logging.StreamHandler(sys.stdout)
    logConsoleHandler.setFormatter(logFormat)
    logger.addHandler(logConsoleHandler)

    bot = BBot(api_key, api_secret, logger)
    bot.run()

if __name__ == "__main__":
    main()