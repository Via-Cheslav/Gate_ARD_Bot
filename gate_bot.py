import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# === Загрузка токена из .env ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# === Создание бота и диспетчера ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === Обработка команды /start ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(f"Привет, {message.from_user.first_name}! Бот работает ✅")

# === Основной цикл ===
async def main():
    print("🚀 Бот запущен. Ожидаем события...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())