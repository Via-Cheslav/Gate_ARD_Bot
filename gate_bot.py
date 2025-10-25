import asyncio
import os
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from dotenv import load_dotenv

# === Загрузка переменных окружения ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPERATORS = os.getenv("OPERATORS", "").split(",") if os.getenv("OPERATORS") else []
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
tasks = {}

# === Основная клавиатура клиента ===
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Прошу открыть въезд 🚗")],
        [KeyboardButton(text="🚗 Прошу открыть выезд")]
    ],
    resize_keyboard=True
)

# === Команда /start ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Выберите действие:",
        reply_markup=main_kb
    )

# === Команда /id ===
@dp.message(Command("id"))
async def get_id(message: types.Message):
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")

# === Команда /help ===
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📘 <b>Справка по управлению воротами</b>\n\n"
        "🔹 <b>Прошу открыть въезд 🚗</b> — отправляет запрос операторам открыть ворота для въезда.\n"
        "🔹 <b>🚗 Прошу открыть выезд</b> — запрос на открытие ворот для выезда.\n\n"
        "🔹 После нажатия оператор получает уведомление и нажимает «Сделано».\n"
        "🔹 Когда ворота открыты, вы получите сообщение с кнопкой «👍 Спасибо».\n"
        "🔹 После «Спасибо» оператору приходит уведомление о благодарности 👏.\n\n"
        "📍 Дополнительные команды:\n"
        "/id — показать ваш Telegram ID\n"
        "/start — перезапуск меню\n"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_kb)

# === Обработка запросов клиента ===
@dp.message(F.text.in_(["Прошу открыть въезд 🚗", "🚗 Прошу открыть выезд"]))
async def handle_request(message: types.Message):
    direction = "въезд" if "въезд" in message.text else "выезд"
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    task_id = str(uuid.uuid4())

    # Клиенту
    user_msg = await message.answer(
        f"[КЛИЕНТ] Заявка направлена операторам. Ожидайте ⏳",
        reply_markup=main_kb
    )

    tasks[task_id] = {
        "user_id": user_id,
        "user_name": user_name,
        "direction": direction,
        "user_msg_id": user_msg.message_id
    }

    # Операторам
    for op_id in OPERATORS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Сделано", callback_data=f"done:{task_id}"),
                InlineKeyboardButton(text="❌ Игнорировать", callback_data=f"ignore:{task_id}")
            ]])
            await bot.send_message(
                int(op_id),
                f"[ОПЕРАТОР] @{user_name} просит открыть {direction}",
                reply_markup=kb
            )
        except Exception as e:
            print(f"[Ошибка уведомления оператору {op_id}]: {e}")

# === Действия оператора ===
@dp.callback_query(F.data.startswith(("done:", "ignore:")))
async def handle_operator_action(callback: types.CallbackQuery):
    action, task_id = callback.data.split(":")
    task = tasks.get(task_id)
    if not task:
        await callback.answer("Заявка уже закрыта или не найдена.")
        return

    user_id = task["user_id"]
    user_name = task["user_name"]
    direction = task["direction"]
    operator_name = callback.from_user.username or callback.from_user.first_name
    task["operator_name"] = operator_name

    # Удаляем сообщение клиента с "Ожидайте"
    user_msg_id = task.get("user_msg_id")
    if user_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=user_msg_id)
        except:
            pass

    if action == "ignore":
        await callback.message.edit_text(f"[ОПЕРАТОР] Заявка от @{user_name} на {direction} была проигнорирована.")
        tasks.pop(task_id, None)
        return

    # Сообщение оператору
    await callback.message.edit_text(
        f"[ОПЕРАТОР] Заявка для @{user_name} на {direction} выполнена."
    )

    # Клиенту
    thank_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Спасибо", callback_data=f"thank:{task_id}")]
    ])
    await bot.send_message(
        user_id,
        f"[КЛИЕНТ] Ворота {direction} открыты оператором @{operator_name}",
        reply_markup=thank_kb
    )

# === Обработка кнопки "Спасибо" ===
@dp.callback_query(F.data.startswith("thank:"))
async def handle_thank(callback: types.CallbackQuery):
    task_id = callback.data.split(":")[1]
    task = tasks.pop(task_id, None)
    if not task:
        await callback.answer("Заявка уже закрыта.")
        return

    user_id = task["user_id"]
    user_name = task["user_name"]
    direction = task["direction"]
    operator_name = task.get("operator_name", "оператор")

    # Убираем сообщение с кнопкой Спасибо
    try:
        await callback.message.delete()
    except:
        pass

    # Отправляем главное меню клиенту
    await bot.send_message(
        user_id,
        f"[КЛИЕНТ] Заявка на {direction} выполнена @{operator_name}",
        reply_markup=main_kb  # Главное меню с кнопками
    )

    # Отправляем уведомление оператору о благодарности
    for op_id in OPERATORS:
        try:
            await bot.send_message(
                int(op_id),
                f"[ОПЕРАТОР] 👏 Спасибо за {direction} от @{user_name}"
            )
        except:
            pass

    # Подтверждаем пользователю, что обратная связь отправлена
    await callback.answer("Обратная связь отправлена.")

async def main():
    print("🚀 Бот запущен. Ожидаем события...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
