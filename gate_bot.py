# UPDATE_LOGGING_v2
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot=bot)

tasks = {}

# === Функция логирования ===
def log(msg):
    print(f"[LOG] {msg}")

# === Общая клавиатура (для клиента и оператора) с машинкой 🚗 ===
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Прошу открыть въезд 🚗")],   # машинка слева
        [KeyboardButton(text="🚗 Прошу открыть выезд")],   # машинка справа
    ],
    resize_keyboard=True
)

# === Команда старт ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    log(f"Старт от {message.from_user.username or message.from_user.first_name}")
    await message.answer(
        "Привет! Выберите действие:",
        reply_markup=main_kb
    )

# === Команда /id для теста ===
@dp.message(Command("id"))
async def get_id(message: types.Message):
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")
    log(f"Запрос ID от {message.from_user.username or message.from_user.first_name}")

# === Команда /help ===
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = ("Использование бота:\n"
            "1. Ворота: Выберите 'Прошу открыть въезд/выезд'\n"
            "2. Оператор: Нажмите 'Сделано' или 'Игнорировать'\n"
            "3. Клиент: Нажмите 'Спасибо' после открытия")
    await message.answer(text)
    log(f"Запрос помощи от {message.from_user.username or message.from_user.first_name}")

# === Обработка запроса на открытие ворот ===
@dp.message(F.text.in_(["Прошу открыть въезд 🚗", "🚗 Прошу открыть выезд"]))
async def handle_request(message: types.Message):
    direction = "въезд" if "въезд" in message.text else "выезд"
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    task_id = str(uuid.uuid4())

    # Клиенту: уведомление о запросе
    user_msg = await message.answer(f"- Заявка направлена операторам. Ждите", reply_markup=main_kb)
    log(f"Заявка {task_id} создана от {user_name} на {direction}")

    tasks[task_id] = {
        "user_id": user_id,
        "user_name": user_name,
        "direction": direction,
        "user_msg_id": user_msg.message_id,
        "operator_msg_ids": []
    }

    # Операторам: уведомление + те же кнопки что у клиента
    for op_id in OPERATORS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Сделано", callback_data=f"done:{task_id}"),
                    InlineKeyboardButton(text="Игнорировать", callback_data=f"ignore:{task_id}")
                ]
            ])
            op_msg = await bot.send_message(
                int(op_id),
                f"> @{user_name} просит открыть {direction}",
                reply_markup=kb
            )
            tasks[task_id]["operator_msg_ids"].append(op_msg.message_id)
            log(f"Уведомление оператору {op_id}, task_id={task_id}")
            # Отправляем оператору те же кнопки, что клиенту
            await bot.send_message(
                int(op_id),
                "Выберите действие:",
                reply_markup=main_kb
            )
        except Exception as e:
            log(f"Ошибка уведомления оператору {op_id}: {e}")

# === Действия оператора ===
@dp.callback_query(F.data.startswith(("done:", "ignore:")))
async def handle_operator_action(callback: types.CallbackQuery):
    action, task_id = callback.data.split(":")
    task = tasks.get(task_id)
    if not task:
        await callback.answer("Заявка уже закрыта или не найдена.")
        log(f"Оператор нажал {action}, но task {task_id} не найден")
        return

    user_id = task["user_id"]
    user_name = task["user_name"]
    direction = task["direction"]
    operator_name = callback.from_user.username or callback.from_user.first_name

    # Удаляем сообщение запроса пользователя
    user_msg_id = task.get("user_msg_id")
    if user_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=user_msg_id)
            log(f"Удалено сообщение пользователя {user_name} task {task_id}")
        except:
            pass

    if action == "ignore":
        # Изменяем сообщение оператора и возвращаем кнопки
        await callback.message.edit_text(f"> Заявка на {direction} проигнорирована")
        await callback.message.answer("Выберите действие:", reply_markup=main_kb)
        log(f"Оператор {operator_name} проигнорировал task {task_id}")
        return

    # Действие “Сделано”
    await callback.message.edit_text(f"> Заявка для @{user_name} на {direction} выполнена")
    log(f"Оператор {operator_name} выполнил task {task_id}")

    # Клиенту: уведомление с кнопкой “Спасибо”
    thank_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Спасибо", callback_data=f"thank:{task_id}")]
    ])
    await bot.send_message(
        user_id,
        f"- Ворота {direction} открыты оператором @{operator_name}",
        reply_markup=thank_kb
    )
    log(f"Сообщение клиенту {user_name} с кнопкой Спасибо, task {task_id}")

# === Клиент нажал Спасибо ===
@dp.callback_query(F.data.startswith("thank:"))
async def handle_thank(callback: types.CallbackQuery):
    task_id = callback.data.split(":")[1]
    task = tasks.pop(task_id, None)
    if not task:
        await callback.answer("Заявка уже закрыта.")
        log(f"Нажата Спасибо для уже закрытой заявки task {task_id}")
        return

    user_id = task["user_id"]
    user_name = task["user_name"]
    direction = task["direction"]
    operator_name = callback.from_user.username or "оператор"

    # Убираем сообщение с кнопкой
    await callback.message.delete()
    await callback.answer("Обратная связь отправлена.")
    log(f"Клиент {user_name} нажал Спасибо, task {task_id}")

    # Клиенту: короткое уведомление + главное меню
    await bot.send_message(
        user_id,
        f"- Заявка на {direction} выполнена @{operator_name}",
        reply_markup=main_kb
    )

    # Операторам: уведомление о благодарности с эмодзи 👏
    for op_id in OPERATORS:
        try:
            await bot.send_message(
                int(op_id),
                f"> 👏 Спасибо за {direction} от @{user_name}"
            )
            log(f"Отправлено спасибо оператору {op_id} за task {task_id}")
        except:
            log(f"Ошибка отправки спасибо оператору {op_id} за task {task_id}")

# === Основной запуск бота ===
async def main():
    log("🚀 Бот запущен. Ожидаем события...")
    await dp.start_polling(skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
