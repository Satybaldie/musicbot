import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Импортируем функции базы данных
from database import init_db, add_user, log_download, get_stats, get_user_history

# 1. Настройка
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Твой ID администратора
YOUR_ADMIN_ID = 5932714152

# Инициализация базы данных
init_db()

# Путь к ffmpeg
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

# 2. Создание главного меню
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = KeyboardButton("🔍 Найти песню")
    btn_downloaded = KeyboardButton("📥 Скачанные")
    btn_wave = KeyboardButton("🌊 Моя волна")
    btn_playlists = KeyboardButton("📂 Мои Плейлисты")
    markup.row(btn_search, btn_downloaded)
    markup.row(btn_wave, btn_playlists)
    return markup

# Настройки маскировки для YouTube
def get_ydl_opts(query_type="yt"):
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
        }
    }
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
    return opts

# Асинхронная загрузка
async def download_logic(query, search_prefix):
    q_type = "yt" if "yt" in search_prefix else "sc"
    search_query = f"{search_prefix}:{query}"
    def run_yt_dlp():
        with yt_dlp.YoutubeDL(get_ydl_opts(q_type)) as ydl:
            info = ydl.extract_info(search_query, download=True)['entries'][0]
            filename = ydl.prepare_filename(info)
            file_path = os.path.splitext(filename)[0] + ".mp3"
            return file_path, info.get('title', 'Music')
    return await asyncio.get_event_loop().run_in_executor(None, run_yt_dlp)

# 3. Обработчики

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    welcome_text = (
        f"👋 **Привет, {message.from_user.first_name}!**\n\n"
        "Я твой **Музыкальный Помощник** 🎧\n"
        "Здесь ты можешь найти свою любимую песню и слушать её бесплатно или скачать.\n"
        "или ты можешь добавить свой плейлист и у меня есть функция моя волна в котором я могу тебе предлагать песню которая может тебе понравиться. 🌊"
    )
    await message.reply(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message_handler(commands=['admin'])
async def admin_stats(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        u_count, d_count = get_stats()
        await message.answer(f"📊 **Статистика:**\n👤 Юзеров: {u_count}\n🎵 Скачано: {d_count}")

@dp.message_handler(commands=['send'])
async def broadcast(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        text = message.get_args()
        if not text: return await message.answer("Пример: `/send Текст`")
        import sqlite3
        conn = sqlite3.connect('users.db')
        users = conn.execute('SELECT user_id FROM users').fetchall()
        conn.close()
        for u in users:
            try:
                await bot.send_message(u[0], text)
                await asyncio.sleep(0.05)
            except: pass
        await message.answer("✅ Рассылка завершена!")

# ИЗМЕНЕННАЯ КНОПКА: Сразу присылает MP3 из истории
@dp.message_handler(lambda message: message.text == "📥 Скачанные")
async def show_history_mp3(message: types.Message):
    history = get_user_history(message.from_user.id)
    if not history:
        return await message.answer("📥 История пока пуста. Найди свою первую песню! 😉")
    
    await message.answer("📥 **Загружаю твои последние песни...**")
    
    for query in history:
        try:
            # Ищем и скачиваем каждую песню из истории
            file_path, title = await download_logic(query, "ytsearch1")
            with open(file_path, 'rb') as audio:
                await message.answer_audio(audio, caption=f"🎶 Из истории: **{title}**")
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            continue # Если какая-то песня не нашлась, просто идем к следующей

@dp.message_handler(lambda message: message.text in ["🔍 Найти песню", "🌊 Моя волна", "📂 Мои Плейлисты"])
async def buttons_help(message: types.Message):
    await message.answer("Просто отправь мне название песни текстом! 👇")

# ГЛАВНЫЙ ПОИСК
@dp.message_handler()
async def main_search(message: types.Message):
    query = message.text
    log_download(message.from_user.id, query)
    status_msg = await message.answer(f"🚀 Ищу: **{query}**...")
    try:
        file_path, title = await download_logic(query, "ytsearch1")
        await status_msg.edit_text("⚡️ Почти готово, отправляю файл...")
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 **{title}**\nПриятного прослушивания!")
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
    except Exception:
        try:
            await status_msg.edit_text("🔍 Пробую резервный поиск...")
            file_path, title = await download_logic(query, "scsearch1")
            with open(file_path, 'rb') as audio:
                await message.answer_audio(audio, caption=f"🎶 **{title}**")
            if os.path.exists(file_path):
                os.remove(file_path)
            await status_msg.delete()
        except:
            await status_msg.edit_text("❌ Не удалось найти эту песню.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)