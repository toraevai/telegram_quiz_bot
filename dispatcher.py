import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import db
from quiz_data import quiz_data
from token import token

API_TOKEN = token

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)

# Объект бота
bot = Bot(token=API_TOKEN)
# Диспетчер
dp = Dispatcher()


# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Начать игру"))
    builder.add(types.KeyboardButton(text="Статистика"))
    await message.answer("Добро пожаловать в квиз!", reply_markup=builder.as_markup(resize_keyboard=True))


# Хэндлер на команду /quiz
@dp.message(F.text == "Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    # Отправляем новое сообщение без кнопок
    await message.answer("Давайте начнем квиз!")
    # Запускаем новый квиз
    await new_quiz(message)


@dp.message(F.text == "Статистика")
@dp.message(Command("statistics"))
async def cmd_statistics(message: types.Message):
    # получаем id пользователя, отправившего сообщение
    user_id = message.from_user.id
    users = await db.get_users()
    if users == 0:
        await message.answer(f"Вы первый участник квиза.")
    else:
        if user_id in users:
            right_answers = await db.get_right_answers(user_id)
            await message.answer(f"Вы ответили правильно на {right_answers} из {len(quiz_data)} вопросов.")
        else:
            await message.answer(f"Вы еще не участвовали в квизе.")
        await message.answer(f"Общее количство участников: {len(users)}.")
        users_with_high_answ = await db.get_users_with_answ_percent(80)
        num_of_high_answ_users = len(users_with_high_answ) if users_with_high_answ != 0 else 0
        await message.answer(
            f"Количество участников, отвтивших на 80% квиза: {num_of_high_answ_users}.")


async def new_quiz(message):
    # получаем id пользователя, отправившего сообщение
    user_id = message.from_user.id
    # сбрасываем значение текущего индекса вопроса квиза в 0
    current_question_index = 0
    right_answers = 0
    await db.update_user_info(user_id, current_question_index, right_answers)

    # запрашиваем новый вопрос для квиза
    await get_question(message, user_id)


async def get_question(message, user_id):
    # Запрашиваем из базы текущий индекс для вопроса
    current_question_index = await db.get_quiz_index(user_id)
    # Получаем список вариантов ответа для текущего вопроса
    opts = quiz_data[current_question_index]['options']
    # Функция генерации кнопок для текущего вопроса квиза
    # В качестве аргументов передаем варианты ответов и значение правильного ответа (не индекс!)
    kb = generate_options_keyboard(opts)
    # Отправляем в чат сообщение с вопросом, прикрепляем сгенерированные кнопки
    await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb)


def generate_options_keyboard(answer_options):
    # Создаем сборщика клавиатур типа Inline
    builder = InlineKeyboardBuilder()

    # В цикле создаем 4 Inline кнопки, а точнее Callback-кнопки
    for option in answer_options:
        builder.add(types.InlineKeyboardButton(
            # Текст на кнопках соответствует вариантам ответов
            text=option,
            # Присваиваем данные для колбэк запроса.
            # Если ответ верный сформируется колбэк-запрос с данными 'right_answer'
            # Если ответ неверный сформируется колбэк-запрос с данными 'wrong_answer'
            callback_data=option)
        )

    # Выводим по одной кнопке в столбик
    builder.adjust(1)
    return builder.as_markup()


@dp.callback_query()
async def answer(callback: types.CallbackQuery):
    await remove_buttons(callback)
    user_id = callback.from_user.id
    # Получение текущего вопроса для данного пользователя
    current_question_index = await db.get_quiz_index(user_id)
    right_answers = await db.get_right_answers(user_id)

    await callback.message.answer(f"Ваш ответ: {callback.data}.")
    # Получаем индекс правильного ответа для текущего вопроса
    correct_index = quiz_data[current_question_index]['correct_option']
    # Получаем список вариантов ответа для текущего вопроса
    opts = quiz_data[current_question_index]['options']
    # Отправляем в чат сообщение, что ответ верный
    if callback.data == opts[correct_index]:
        await callback.message.answer("Верно!")
        await db.update_user_info(user_id, current_question_index, right_answers + 1)
    else:
        await callback.message.answer(
            f"Неправильно. Правильный ответ: {quiz_data[current_question_index]['options'][correct_index]}.")

    # Обновляем информацию по правильным ответам
    right_answers = await db.get_right_answers(user_id)
    # Увеличиваем индекс
    current_question_index += 1
    await db.update_user_info(callback.from_user.id, current_question_index, right_answers)

    # Проверяем достигнут ли конец квиза
    await check_end(current_question_index, callback)


async def remove_buttons(callback):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )


async def check_end(current_question_index, callback):
    if current_question_index < len(quiz_data):
        # Следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        # Уведомление об окончании квиза
        right_answers = await db.get_right_answers(callback.from_user.id)
        await callback.message.answer("Это был последний вопрос. Квиз завершен!")
        await callback.message.answer(f"Вы ответили правильно на {right_answers} из {len(quiz_data)} вопросов.")


async def run_dispatcher():
    await db.create_table()
    await dp.start_polling(bot)
