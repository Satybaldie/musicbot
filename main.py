import os
import asyncio
import yt_dlp
import requests
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_user, log_download, get_user_history, add_to_playlist, get_user_playlist

# Инициализация кэша
def init_cache_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS file_cache (query TEXT PRIMARY KEY, file_id TEXT, title TEXT)')
    conn.commit()
    conn.close()

init_cache_db()
init_db()

TOKEN = os.getenv('BOT_TOKEN')
GOOGLE_API_KEY = "AIzaSyBPqLNBRJAXxv4HyMO-WMFMns95YccOB2c"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")
COOKIE_FILES = ['cookies1.txt', 'cookies2.txt', 'cookies3.txt']

# --- ФУНКЦИИ ДЛЯ КНОПОК ---

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔍 Найти песню"), KeyboardButton("📥 Скачанные"))
    markup.row(KeyboardButton("🌊 Моя волна"), KeyboardButton("📂 Мои Плейлисты"))
    return markup

def get_song_keyboard(title):
    markup = InlineKeyboardMarkup()
    # КРИТИЧНО: Обрезаем название до 20 символов, чтобы не превысить лимит Telegram (64 байта)
    safe_title = title[:20].strip()
    markup.add(
        InlineKeyboardButton("➕ В плейлист", callback_data=f"pl_{safe_title}"),
        InlineKeyboardButton("📥 В скачанные", callback_data=f"dl_{safe_title}")
    )
    return markup

# --- ОБРАБОТЧИК КНОПОК (С защитой от лагов) ---

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def process_callback(call: types.CallbackQuery):
    try:
        action = call.data[:2]
        song_name = call.data[3:]
        
        if action == "pl":
            add_to_playlist(call.from_user.id, song_name)
            await call.answer(f"🎶 Добавлено: {song_name}")
        elif action == "dl":
            log_download(call.from_user.id, song_name)
            await call.answer(f"📥 Сохранено в историю")
            
    except Exception as e:
        print(f"Ошибка кнопки: {e}")
        await call.answer("❌ Ошибка базы данных", show_alert=True)

# --- ЛОГИКА СКАЧИВАНИЯ (Ускоренная) ---

def get_from_cache(query):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, title FROM file_cache WHERE query LIKE ?', (f"%{query}%",))
        res = cursor.fetchone()
        conn.close()
        return res
    except: return None

def save_to_cache(query, file_id, title):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO file_cache VALUES (?, ?, ?)', (query, file_id, title))
        conn.commit()
        conn.close()
    except: pass

async def download_audio(query):
    # 1. Проверяем кэш
    cached = get_from_cache(query)
    if cached: return "cache", cached[0], cached[1]

    # 2. Очередь поиска
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
        'quiet': True,
        'no_warnings': True
    }

    # Пробуем по очереди все доступные куки
    for c_file in COOKIE_FILES:
        if os.path.exists(c_file):
            try:
                def run_yt():
                    opts = ydl_opts.copy()
                    opts['cookiefile'] = c_file
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                        entry = info['entries'][0]
                        path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
                        return path, entry.get('title', 'Music')
                return await asyncio.get_event_loop().run_in_executor(None, run_yt)
            except: continue

    # 3. Резерв: SoundCloud
    def run_sc():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            entry = info['entries'][0]
            path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
            return path, entry.get('title', 'Music')
    return await asyncio.get_event_loop().run_in_executor(None, run_sc)

# --- ОСНОВНЫЕ КОМАНДЫ ---

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("🚀 Бот обновлен! Кнопки теперь работают стабильно.", reply_markup=get_main_menu())

@dp.message_handler()
async def search_handler(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]:
        return await message.answer("Напиши название трека:")
    
    if message.text == "📂 Мои Плейлисты":
        songs = get_user_playlist(message.from_user.id)
        if not songs: return await message.answer("Плейлист пуст.")
        for s in songs:
            res = await download_audio(s)
            if res:
                if res[0] == "cache":
                    await bot.send_audio(message.chat.id, res[1], caption=f"🎶 {res[2]}", reply_markup=get_song_keyboard(res[2]))
                else:
                    path, title = res
                    with open(path, 'rb') as f:
                        msg = await bot.send_audio(message.chat.id, f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
                        save_to_cache(s, msg.audio.file_id, title)
                    if os.path.exists(path): os.remove(path)
        return

    # Обычный поиск
    status = await message.answer("🔎 Ищу...")
    try:
        res = await download_audio(message.text)
        if res[0] == "cache":
            await bot.send_audio(message.chat.id, res[1], caption=f"🎶 {res[2]}", reply_markup=get_song_keyboard(res[2]))
        else:
            path, title = res
            with open(path, 'rb') as f:
                msg = await bot.send_audio(message.chat.id, f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
                save_to_cache(message.text, msg.audio.file_id, title)
            if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        await status.edit_text("❌ Ошибка поиска.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)