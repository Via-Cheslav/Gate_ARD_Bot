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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot=bot)

tasks = {}  # Словарь текущих задач, только новые заявки

# === Основная клавиатура клиента с кнопками ===
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Прошу открыть ворота ВЪЕЗД 🚗")],
        [KeyboardButton(text="🚗 Прошу открыть ворота ВЫЕЗД")],
    ],
    resize_keyboard=True
)

# === /start ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Выберите действие (или отправьте цифру):\n"
        "1 — Въезд\n"
        "2 — Выезд",
        reply_markup=main_kb
    )

# === /help ===
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "🔹 Бот управления воротами\n"
        "Кнопки или цифры можно использовать для действий:\n"
        "1 — Прошу открыть ворота ВЪЕЗД\n"
        "2 — Прошу открыть ворота ВЫЕЗД\n"
        "3 — Выполнено (для оператора)\n"
        "4 — Спасибо (для клиента)\n\n"
        "Команды:\n"
        "/start — показать главное меню\n"
        "/id — показать ваш Telegram ID\n"
        "/help — показать эту инструкцию"
    )
    await message.answer(help_text)

# === /id ===
@dp.message(Command("id"))
async def get_id(message: types.Message):
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")

# === Обработка кнопок и цифр ===
@dp.message()
async def handle_request(message: types.Message):
    text = message.text.strip()
    # Определяем действие пользователя
    if text in ["Прошу открыть ворота ВЪЕЗД 🚗", "1"]:
        direction = "въезд"
    elif text in ["🚗 Прошу открыть ворота ВЫЕЗД", "2"]:
        direction = "выезд"
    else:
        return  # Другие сообщения игнорируем

    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    task_id = str(uuid.uuid4())

    # Клиенту: уведомление о запросе
    user_msg = await message.answer(
        f"[КЛИЕНТ] Заявка направлена операторам. Ждите",
        reply_markup=main_kb
    )

    tasks[task_id] = {
        "user_id": user_id,
        "user_name": user_name,
        "direction": direction,
        "user_msg_id": user_msg.message_id,
        "operator_done_msg_id": None,
        "operator_name": None
    }

    # Оператору (тот же аккаунт)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Выполнено", callback_data=f"done:{task_id}"),
            InlineKeyboardButton(text="Пропустить", callback_data=f"ignore:{task_id}")
        ]
    ])
    await bot.send_message(
        user_id,
        f"[ОПЕРАТОР] @{user_name} просит открыть ворота {direction}\n(или отправьте 3 — Выполнено)",
        reply_markup=kb
    )

# === Обработка действий оператора и кнопок ===
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

    if action == "ignore":
        await callback.message.edit_text(f"[ОПЕРАТОР] Заявка на {direction} была пропущена")
        tasks.pop(task_id)
        return

    # Создаём сообщение о выполнении
    done_msg = await bot.send_message(
        user_id,
        f"[ОПЕРАТОР] Заявка для @{user_name} на {direction} выполнена ✅\n(Отправьте 4 — Спасибо)"
    )
    task["operator_done_msg_id"] = done_msg.message_id

    # Клиенту: уведомление с кнопкой Спасибо
    thank_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Спасибо", callback_data=f"thank:{task_id}")]
    ])
    await bot.send_message(
        user_id,
        f"[КЛИЕНТ] Ворота {direction} открыты оператором @{operator_name}",
        reply_markup=thank_kb
    )

# === Обработка Спасибо через кнопку или цифру 4 ===
@dp.message(F.text.in_(["4"]))
async def handle_thank_number(message: types.Message):
    # Ищем последнюю задачу для этого пользователя
    task_id = None
    for tid, t in tasks.items():
        if t["user_id"] == message.from_user.id:
            task_id = tid
    if not task_id:
        await message.answer("Нет активной заявки для благодарности.")
        return

    await handle_thank_by_id(message, task_id)

@dp.callback_query(F.data.startswith("thank:"))
async def handle_thank(callback: types.CallbackQuery):
    task_id = callback.data.split(":")[1]
    await handle_thank_by_id(callback, task_id)

async def handle_thank_by_id(obj, task_id):
    task = tasks.pop(task_id, None)
    if not task:
        if isinstance(obj, types.CallbackQuery):
            await obj.answer("Заявка уже закрыта.")
        else:
            await obj.answer("Заявка уже закрыта.")
        return

    user_id = task["user_id"]
    user_name = task["user_name"]
    direction = task["direction"]
    operator_name = task.get("operator_name", "оператор")
    operator_done_msg_id = task.get("operator_done_msg_id")

    # Удаляем сообщение с кнопкой Спасибо
    if isinstance(obj, types.CallbackQuery):
        await obj.message.delete()
        await obj.answer("Обратная связь отправлена.")

    # Клиенту: уведомление + главное меню
    await bot.send_message(
        user_id,
        f"[КЛИЕНТ] Заявка на {direction} выполнена @{operator_name}",
        reply_markup=main_kb
    )

    # Оператору: удаляем сообщение о выполнении и благодарим
    if operator_done_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=operator_done_msg_id)
        except:
            pass
    await bot.send_message(
        user_id,
        f"[ОПЕРАТОР] 👏 Спасибо за {direction} от @{user_name}"
    )

# === Основной цикл ===
async def main():
    print("Бот запущен. Ожидаем события...")
    await dp.start_polling(skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
