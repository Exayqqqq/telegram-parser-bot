
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from telegram_parser_bot import run_parser_for_user  # Импорт парсера

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Отправь команду /parse чтобы получить свежие объявления.")

@dp.message(Command("parse"))
async def cmd_parse(message: Message):
    user_id = str(message.from_user.id)
    await message.answer("🔍 Начинаю парсинг, подожди немного...")

    async for link in run_parser_for_user(user_id):
        if link:
            await message.answer(f"🔗 <a href='{link}'>Новое объявление</a>")
    else:
        await message.answer("✅ Парсинг завершён или доступ запрещён.")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
