from aiogram import Bot
import os
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))

async def main():
    me = await bot.get_me()
    print(me)

import asyncio
asyncio.run(main())
