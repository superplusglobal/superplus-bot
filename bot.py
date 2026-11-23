import os
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNELS = [
    x.strip() for x in os.getenv("CHANNELS", "").split(",") if x.strip()
]

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

bot = Bot(token=TOKEN)
dp = Dispatcher()
db = sqlite3.connect("superplus.db")
db.execute("""
CREATE TABLE IF NOT EXISTS content (
    code TEXT PRIMARY KEY,
    chat_id INTEGER,
    message_id INTEGER
)
""")
db.commit()

pending = {}

async def is_member(user_id):
    if not CHANNELS:
        return False
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True

@dp.message(CommandStart())
async def start(message: Message):
    if await is_member(message.from_user.id):
        await message.answer(
            "به Super Plus خوش آمدید!\n"
            "برای دریافت محتوا، کد آن را با دستور /get بفرستید.\n"
            "مثال: /get video1"
        )
    else:
        links = "\n".join(CHANNELS)
        await message.answer(
            "برای استفاده از ربات، ابتدا عضو هر چهار کانال شوید:\n"
            f"{links}\n\n"
            "پس از عضویت دوباره /start را بزنید."
        )

@dp.message(Command("save"))
async def save_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("استفاده: /save video1")
        return
    pending[message.from_user.id] = parts[1].strip()
    await message.answer("حالا فایل یا ویدیوی قانونی را بفرست.")

@dp.message(F.video | F.document | F.photo)
async def receive_content(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    code = pending.pop(message.from_user.id, None)
    if not code:
        return
    db.execute(
        "INSERT OR REPLACE INTO content VALUES (?, ?, ?)",
        (code, message.chat.id, message.message_id)
    )
    db.commit()
    await message.answer(f"محتوا با کد {code} ذخیره شد.")

@dp.message(Command("get"))
async def get_content(message: Message):
    if not await is_member(message.from_user.id):
        await message.answer("ابتدا عضو هر چهار کانال شوید و دوباره /start را بزنید.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("مثال: /get video1")
        return

    row = db.execute(
        "SELECT chat_id, message_id FROM content WHERE code = ?",
        (parts[1].strip(),)
    ).fetchone()

    if not row:
        await message.answer("این محتوا پیدا نشد.")
        return

    try:
        sent = await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=row[0],
            message_id=row[1]
        )
        await asyncio.sleep(20)
        await bot.delete_message(message.chat.id, sent.message_id)
    except TelegramBadRequest:
        await message.answer("ارسال یا حذف پیام انجام نشد.")

async def main():
    print("Super Plus bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
