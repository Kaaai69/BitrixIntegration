import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from config import (
    BOT_TOKEN,
    BITRIX_WEBHOOK_URL,
    BITRIX_DEFAULT_CURRENCY,
    BITRIX_DEFAULT_CATEGORY_ID,
)
from bitrix_client import BitrixClient, BitrixError


logging.basicConfig(level=logging.INFO)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

bitrix = BitrixClient(BITRIX_WEBHOOK_URL)


class DealForm(StatesGroup):
    name = State()
    phone = State()
    email = State()
    service = State()
    budget = State()
    comment = State()
    confirm = State()


def normalize_text(value: str) -> str:
    return value.strip()


def is_skip(value: str) -> bool:
    return value.strip().lower() in {"-", "нет", "пропустить", "skip"}


def validate_phone(phone: str) -> bool:
    """
    Простая проверка телефона.
    Разрешаем цифры, +, пробелы, скобки и дефисы.
    """
    pattern = r"^\+?[0-9\s\-\(\)]{7,20}$"
    return bool(re.match(pattern, phone))


def validate_email(email: str) -> bool:
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email))


def parse_budget(value: str) -> float | None:
    """
    Превращаем строку бюджета в число.
    Примеры:
    '100000' -> 100000.0
    '100 000' -> 100000.0
    '100000.50' -> 100000.50
    '-' -> None
    """
    if is_skip(value):
        return None

    cleaned = value.replace(" ", "").replace(",", ".")

    try:
        budget = float(cleaned)
    except ValueError:
        return None

    if budget < 0:
        return None

    return budget


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать сделку")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подтвердить")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Привет! Я помогу создать сделку в Bitrix24 CRM.\n\n"
        "Нажми «Создать сделку», и я по шагам соберу данные клиента.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("cancel"))
@dp.message(F.text.lower() == "отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Действие отменено.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == "Создать сделку")
async def create_deal_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(DealForm.name)

    await message.answer(
        "Введите имя клиента.\n\n" "Например: Иван Петров",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(DealForm.name)
async def process_name(message: Message, state: FSMContext):
    name = normalize_text(message.text or "")

    if len(name) < 2:
        await message.answer(
            "Имя слишком короткое. Введите имя клиента еще раз."
        )
        return

    await state.update_data(name=name)
    await state.set_state(DealForm.phone)

    await message.answer(
        "Введите телефон клиента.\n\n"
        "Например: +7 999 123-45-67\n"
        "Если телефона нет, напишите «-»."
    )


@dp.message(DealForm.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = normalize_text(message.text or "")

    if is_skip(phone):
        phone = None
    elif not validate_phone(phone):
        await message.answer(
            "Телефон выглядит некорректно.\n"
            "Введите телефон еще раз или напишите «-», если телефона нет."
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(DealForm.email)

    await message.answer(
        "Введите email клиента.\n\n"
        "Например: client@example.com\n"
        "Если email нет, напишите «-»."
    )


@dp.message(DealForm.email)
async def process_email(message: Message, state: FSMContext):
    email = normalize_text(message.text or "")

    if is_skip(email):
        email = None
    elif not validate_email(email):
        await message.answer(
            "Email выглядит некорректно.\n"
            "Введите email еще раз или напишите «-», если email нет."
        )
        return

    await state.update_data(email=email)
    await state.set_state(DealForm.service)

    await message.answer(
        "Что нужно клиенту?\n\n"
        "Например: строительство дома, консультация, расчет стоимости, ремонт, аудит проекта."
    )


@dp.message(DealForm.service)
async def process_service(message: Message, state: FSMContext):
    service = normalize_text(message.text or "")

    if len(service) < 3:
        await message.answer("Опишите запрос клиента чуть подробнее.")
        return

    await state.update_data(service=service)
    await state.set_state(DealForm.budget)

    await message.answer(
        "Введите примерный бюджет.\n\n"
        "Например: 1500000\n"
        "Если бюджет неизвестен, напишите «-»."
    )


@dp.message(DealForm.budget)
async def process_budget(message: Message, state: FSMContext):
    raw_budget = normalize_text(message.text or "")
    budget = parse_budget(raw_budget)

    if budget is None and not is_skip(raw_budget):
        await message.answer(
            "Бюджет нужно ввести числом.\n\n"
            "Например: 1500000\n"
            "Или напишите «-», если бюджет неизвестен."
        )
        return

    await state.update_data(budget=budget)
    await state.set_state(DealForm.comment)

    await message.answer(
        "Добавьте комментарий к сделке.\n\n"
        "Например: клиент хочет обсудить сроки на следующей неделе.\n"
        "Если комментария нет, напишите «-»."
    )


@dp.message(DealForm.comment)
async def process_comment(message: Message, state: FSMContext):
    comment = normalize_text(message.text or "")

    if is_skip(comment):
        comment = None

    await state.update_data(comment=comment)
    data = await state.get_data()

    budget_text = (
        f"{data['budget']:.2f} {BITRIX_DEFAULT_CURRENCY}"
        if data.get("budget") is not None
        else "не указан"
    )

    summary = (
        "Проверьте данные перед созданием сделки:\n\n"
        f"Имя: {data.get('name')}\n"
        f"Телефон: {data.get('phone') or 'не указан'}\n"
        f"Email: {data.get('email') or 'не указан'}\n"
        f"Запрос: {data.get('service')}\n"
        f"Бюджет: {budget_text}\n"
        f"Комментарий: {data.get('comment') or 'не указан'}\n\n"
        "Создать сделку в Bitrix24?"
    )

    await state.set_state(DealForm.confirm)
    await message.answer(summary, reply_markup=confirm_keyboard())


@dp.message(DealForm.confirm, F.text == "Подтвердить")
async def process_confirm(message: Message, state: FSMContext):
    data = await state.get_data()

    name = data["name"]
    phone = data.get("phone")
    email = data.get("email")
    service = data["service"]
    budget = data.get("budget")
    comment = data.get("comment")

    deal_title = f"Заявка из Telegram: {name}"

    try:
        contact_id = await bitrix.create_contact(
            name=name,
            phone=phone,
            email=email,
            comment="Контакт создан из Telegram-бота",
        )

        deal_id = await bitrix.create_deal(
            title=deal_title,
            contact_id=contact_id,
            service=service,
            budget=budget,
            currency=BITRIX_DEFAULT_CURRENCY,
            category_id=BITRIX_DEFAULT_CATEGORY_ID,
            comment=comment,
        )

    except BitrixError as error:
        await message.answer(
            "Не удалось создать сделку в Bitrix24.\n\n"
            f"Ошибка Bitrix24:\n{error}",
            reply_markup=main_keyboard(),
        )
        await state.clear()
        return

    except Exception as error:
        logging.exception("Unexpected error")
        await message.answer(
            "Произошла непредвиденная ошибка при создании сделки.\n\n"
            f"{error}",
            reply_markup=main_keyboard(),
        )
        await state.clear()
        return

    await state.clear()

    await message.answer(
        "Сделка успешно создана в Bitrix24.\n\n"
        f"ID контакта: {contact_id}\n"
        f"ID сделки: {deal_id}",
        reply_markup=main_keyboard(),
    )


@dp.message(DealForm.confirm)
async def process_wrong_confirm(message: Message):
    await message.answer(
        "Нажмите «Подтвердить», чтобы создать сделку, или «Отмена», чтобы отменить.",
        reply_markup=confirm_keyboard(),
    )


@dp.message()
async def unknown_message(message: Message):
    await message.answer(
        "Я не понял команду.\n\n"
        "Нажмите «Создать сделку» или отправьте /start.",
        reply_markup=main_keyboard(),
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
