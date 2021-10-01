"""
Binance Telegram Bot for Trading
Notifying Crossover using Exponential Moving Average (EMA)

Author : Nico Renaldo
"""

import os
import sys
import json
import redis
import logging
import pandas as pd
from fp.fp import FreeProxy
from dotenv import load_dotenv
from binance.client import Client
from backtesting.lib import crossover, cross
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Local Variable
load_dotenv()

mode = os.environ.get('mode')
api_key = os.environ.get('binance_api')
api_secret = os.environ.get('binance_secret')
teletoken = os.environ.get('teletoken')
REDIS_URL = os.environ.get("REDISTOGO_URL")

# Redis Database
r = redis.from_url(REDIS_URL)
db_keys = r.keys(pattern='*')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

### EMA Config
emaShortNumber = 5
emaLongNumber = 13

### Save State
symbols = {
    "ETHUSDT":0,
    "BNBUSDT":0,
}


### Telegram Response
if mode == "dev":
    def run(updater):
        updater.start_polling()
elif mode == "prod":
    def run(updater):
        PORT = int(os.environ.get("PORT", "8443"))
        HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
        # Code from https://github.com/python-telegram-bot/python-telegram-bot/wiki/Webhooks#heroku
        print(PORT)
        updater.start_webhook(listen="0.0.0.0",
                              port=PORT,
                              url_path=teletoken,
                              webhook_url="https://{}.herokuapp.com/{}".format(HEROKU_APP_NAME, teletoken))
else:
    logger.error("No MODE specified!")
    sys.exit(1)
def start(update, context):
    """Send a message when the command /start is issued."""
    logger.info("User {} started bot".format(update.effective_user["id"]))
    update.message.reply_text('Welcome to the bot')
    user_id = update.message.from_user.id
    user_name = update.message.from_user.name
    r.set(user_name, user_id)
def exit(update, context):
    """Send a message when the command /start is issued."""
    logger.info("User {} exited".format(update.effective_user["id"]))
    update.message.reply_text('Goodbye')
    user_name = update.message.from_user.name
    r.delete(user_name)
def help(update, context):
    """Send a message when the command /help is issued."""
    logger.info("User {} need help".format(update.effective_user["id"]))
    update.message.reply_text('Help!')
def echo(update, context):
    """Echo the user message."""
    logger.info("User {} echoing bot".format(update.effective_user["id"]))
    update.message.reply_text(update.message.text)
def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)
def checkPrice(update, context):
    """Check Coins Price."""
    message = ""
    for coin in symbols:
        lastPrice = checkPriceCoin(coin)
        message += "%s Last Price : %.2f\n"%(coin, lastPrice[0])
    logger.info(message)
    update.message.reply_text(message)
def routine(context: CallbackContext):
    for coin in symbols:
        cross, lastPrice = checkCross(coin)
        if(cross):
            if(symbols[coin] == 0):
                message = "%s EMA Crossed, Last Price %s"%(coin, lastPrice)
                logger.info("EMA Crossed")
                symbols[coin] = 1
                # send message to all users
                for keys in r.keys(pattern='*'):
                    id = r.get(keys).decode("UTF-8")
                    context.bot.send_message(chat_id=id, text=message)
            else:
                logger.info("%s EMA Crossed but already announced"%coin)
        else:
            symbols[coin] = 0
            logger.info("%s EMA No Cross"%coin)
def startTele():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(teletoken, use_context=True)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("exit", exit))
    dp.add_handler(CommandHandler("price", checkPrice))
    dp.add_handler(CommandHandler("help", help))
    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, echo))
    # log all errors
    dp.add_error_handler(error)
    # Add Scheduler
    j = updater.job_queue
    j.run_repeating(routine, interval=300, first=10)
    # Start the Bot
    run(updater)
    # updater.start_polling()
    # updater.idle()

### Binance Functions
def setupBinance():
    # proxies = {
    #     'http': proxy,
    #     'https': proxy
    # }
    # client = Client(api_key, api_secret, {'proxies': proxies})
    client = Client(api_key, api_secret)
    return client
def EMA(values, n):
    return pd.Series(values).ewm(span=n, adjust=False).mean()
def checkCross(symbol):
    data = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_30MINUTE, "1 day ago UTC")
    df = pd.DataFrame(data)
    df = df.loc[:,4].astype('float32')
    emaShort = EMA(df, emaShortNumber)
    emaLong = EMA(df, emaLongNumber)
    return cross(emaShort, emaLong), df.iloc[-1]
def checkPriceCoin(symbol):
    data = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_30MINUTE, "1 hour ago UTC")
    df = pd.DataFrame(data[-1])
    return df.loc[4].astype("float32")

if __name__ == '__main__':
    # proxy = FreeProxy().get()
    client = setupBinance()
    startTele()