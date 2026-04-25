import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from database import init_db, add_user, log_download, get_stats, get_user_history

# Настройки
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

YOUR_ADMIN_ID = 5932714152
init_db()
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

# Клавиатура
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔍 Найти песню"), KeyboardButton("📥 Скачанные"))
    markup.row(KeyboardButton("🌊 Моя волна"), KeyboardButton("📂 Мои Плейлисты"))
    return markup

# Опции загрузки
def get_ydl_opts():
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
    }
    if os.path.exists('cookies.txt'): opts['cookiefile'] = 'cookies.txt'
    return opts

# Фоновая функция скачивания
async def fast_download(query, prefix="ytsearch1"):
    def run():
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(f"{prefix}:{query}", download=True)['entries'][0]
            path = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"
            return path, info.get('title', 'Music')
    return await asyncio.get_event_loop().run_in_executor(None, run)

# Обработка команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.reply(f"👋 Привет! Я твой Музыкальный Помощник 🎧", reply_markup=get_main_menu())

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        u, d = get_stats()
        await message.answer(f"📊 Юзеров в базе: {u}\n🎵 Всего скачано: {d}")

@dp.message_handler(commands=['send'])
async def cmd_send(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        text = message.get_args()
        if not text: return await message.answer("Используй: /send Текст")
        import sqlite3
        conn = sqlite3.connect('users.db')
        users = conn.execute('SELECT user_id FROM users').fetchall(); conn.close()
        for u in users:
            try: await bot.send_message(u[0], text); await asyncio.sleep(0.05)
            except: pass
        await message.answer("✅ Рассылка завершена!")

# КНОПКА СКАЧАННЫЕ (MP3 ИЗ ИСТОРИИ)
@dp.message_handler(lambda m: m.text == "📥 Скачанные")
async def btn_history(message: types.Message):
    history = get_user_history(message.from_user.id)
    if not history:
        return await message.answer("📥 История пуста. Сначала скачай любую песню!")

    await message.answer("📥 Поднимаю архивы... Сейчас пришлю MP3 из твоей истории!")
    for q in history:
        try:
            path, title = await fast_download(q)
            with open(path, 'rb') as f:
                await message.answer_audio(f, caption=f"🎶 Из истории: **{title}**")
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler(lambda m: m.text in ["🔍 Найти песню", "🌊 Моя волна", "📂 Мои Плейлисты"])
async def btn_help(message: types.Message):
    await message.answer("🎵 Просто напиши название песни прямо в чат!")

# ГЛАВНЫЙ ПОИСК
@dp.message_handler()
async def search(message: types.Message):
    query = message.text
    log_download(message.from_user.id, query) # Запись в историю
    
    status = await message.answer(f"🚀 Ищу: **{query}**...")
    try:
        path, title = await fast_download(query)
        await status.edit_text("⚡️ Отправляю...")
        with open(path, 'rb') as f:
            await message.answer_audio(f, caption=f"🎶 **{title}**")
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        try:
            await status.edit_text("🔍 Пробую резервный источник...")
            path, title = await fast_download(query, "scsearch1")
            with open(path, 'rb') as f:
                await message.answer_audio(f, caption=f"🎶 **{title}**")
            if os.path.exists(path): os.remove(path)
            await status.delete()
        except:
            await status.edit_text("❌ Не удалось найти песню.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)