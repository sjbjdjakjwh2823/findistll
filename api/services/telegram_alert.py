import os
import logging
import asyncio
from telegram import Bot

logger = logging.getLogger(__name__)

class TelegramAlerter:
    def __init__(self, token=None, chat_id=None):
        from dotenv import load_dotenv
        load_dotenv()
        self.token = token or os.getenv("TELEGRAM_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.bot = None
        
        if self.token:
            self.bot = Bot(token=self.token)
        else:
            logger.warning("TELEGRAM_TOKEN not set. Alerting disabled.")

    async def send_alert(self, message):
        """
        Sends an alert message to the configured Telegram chat.
        """
        if not self.bot or not self.chat_id:
            return
            
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=f"🚨 [FinDistill Alert] 🚨\n{message}")
            logger.info("Telegram alert sent.")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    def send_alert_sync(self, message):
        """
        Synchronous wrapper for sending alerts.
        """
        if not self.bot or not self.chat_id:
            return
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.send_alert(message))
            loop.close()
        except Exception as e:
            logger.error(f"Failed to send Telegram alert (Sync): {e}")
