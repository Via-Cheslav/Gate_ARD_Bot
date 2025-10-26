import asyncio
import os
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

# === Загрузка переменных окружения ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPERATORS = os.getenv("OPERATORS", "").split(",") if os.getenv("OPERATORS") else []
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# === Создание бота и диспетчера ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()  # dispatcher пустой, передадим bot в start_polling

tasks = {}

# === Основная клавиатура (кнопки с машинкой 🚗) ===
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Прошу открыть въезд 🚗")],
        [KeyboardButton(text="🚗 Прошу открыть выезд")],
    ],
    resize_keyboard=True
)

# === Команды ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Выберите действие:",
        reply_markup=main_kb
    )

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "Команды:\n"
        "/start — показать клавиатуру\n"
        "/id — показать свой Telegram ID\n"
        "Кнопки:\n"
        "🚗 Прошу открыть въезд/выезд — запросить открытие ворот\n"
        "Сделано — оператор подтверждает выполнение\n"
        "👍 Спасибо — клиент благодарит после открытия\n"
        "Игнорировать — оператор игнорирует запрос"
    )
    await message.answer(text)

# === Обработка запросов клиента ===
@dp.message(F.text.in_(["Прошу открыть въезд 🚗", "🚗 Прошу открыть выезд"]))
async def handle_request(message: types.Message):
    direction = "въезд" if "въезд" in message.text else "выезд"
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    task_id = str(uuid.uuid4())

    # Клиенту: уведомление
    user_msg = await message.answer(
        "Заявка направлена операторам. Ждите",
        reply_markup=main_kb
    )

    tasks[task_id] = {
        "user_id": user_id,
        "user_name": user_name,
        "direction": direction,
        "user_msg_id": user_msg.message_id
    }

    # Операторам: уведомление с кнопками
    for op_id in OPERATORS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Сделано", callback_data=f"done:{task_id}"),
                    InlineKeyboardButton(text="Игнорировать", callback_data=f"ignore:{task_id}")
                ]
            ])
            await bot.send_message(
                int(op_id),
                f"-> @{user_name} просит открыть {direction}",
                reply_markup=kb
            )
        except Exception as e:
            print(f"[LOG] Ошибка уведомления оператору {op_id}: {e}")

# === Обработка действий операторов ===
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

    # Удаляем сообщение запроса клиента
    user_msg_id = task.get("user_msg_id")
    if user_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=user_msg_id)
        except:
            pass

    if action == "ignore":
        await callback.message.edit_text(f"-> Заявка на {direction} была проигнорирована")
        await callback.message.answer("Выберите действие:", reply_markup=main_kb)
        tasks.pop(task_id)
        return

    # Сделано
    await callback.message.edit_text(f"-> Заявка для @{user_name} на {direction} выполнена")
    task["operator_name"] = operator_name  # сохраняем для благодарности

    # Клиенту: уведомление с кнопкой Спасибо
    thank_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Спасибо", callback_data=f"thank:{task_id}")]
    ])
    await bot.send_message(
        user_id,
        f"Ворота {direction} открыты оператором @{operator_name}",
        reply_markup=thank_kb
    )

# === Обработка благодарности клиента ===
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
    await callback.message.delete()
    await callback.answer("Обратная связь отправлена.")

    # Клиенту: уведомление + главная клавиатура
    await bot.send_message(
        user_id,
        f"Заявка на {direction} выполнена @{operator_name}",
        reply_markup=main_kb
    )

    # Операторам: уведомление о благодарности
    for op_id in OPERATORS:
        try:
            await bot.send_message(
                int(op_id),
                f"-> 👏 Спасибо за {direction} от @{user_name}"
            )
        except:
            pass

# === Основной цикл ===
async def main():
    print("[LOG] 🚀 Бот запущен. Ожидаем события...")
    await dp.start_polling(bot, skip_updates=True)  # здесь передаём bot

if __name__ == "__main__":
    asyncio.run(main())
