import os
import asyncio
import yt_dlp
import requests
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_user, log_download, get_user_history, add_to_playlist, get_user_playlist

# Инициализация доп. таблицы для кэша
def init_cache_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS file_cache (query TEXT PRIMARY KEY, file_id TEXT, title TEXT)')
    conn.commit()
    conn.close()

init_cache_db()

TOKEN = os.getenv('BOT_TOKEN')
GOOGLE_API_KEY = "AIzaSyBPqLNBRJAXxv4HyMO-WMFMns95YccOB2c"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")
COOKIE_FILES = ['cookies1.txt', 'cookies2.txt', 'cookies3.txt']

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔍 Найти песню"), KeyboardButton("📥 Скачанные"))
    markup.row(KeyboardButton("🌊 Моя волна"), KeyboardButton("📂 Мои Плейлисты"))
    return markup

def get_song_keyboard(title):
    markup = InlineKeyboardMarkup()
    clean_title = title[:30]
    markup.add(
        InlineKeyboardButton("➕ В плейлист", callback_data=f"pl_{clean_title}"),
        InlineKeyboardButton("📥 В скачанные", callback_data=f"dl_{clean_title}")
    )
    return markup

# --- ФУНКЦИИ КЭША ---
def get_from_cache(query):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT file_id, title FROM file_cache WHERE query = ?', (query,))
    res = cursor.fetchone()
    conn.close()
    return res

def save_to_cache(query, file_id, title):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO file_cache VALUES (?, ?, ?)', (query, file_id, title))
    conn.commit()
    conn.close()

# --- ЛОГИКА СКАЧИВАНИЯ ---
def get_ydl_opts(cookie_file=None):
    return {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
        'external_downloader': 'aria2c', # Ускоряет загрузку, если aria2 установлен
        'external_downloader_args': ['-x', '16', '-s', '16', '-k', '1M'],
    }

async def download_audio(query):
    # 0. Проверяем кэш (МГНОВЕННО)
    cached = get_from_cache(query)
    if cached:
        return "cache", cached[0], cached[1]

    # 1. Попытка через куки (как раньше)
    for c_file in COOKIE_FILES:
        if os.path.exists(c_file):
            try:
                def run_yt():
                    with yt_dlp.YoutubeDL(get_ydl_opts(c_file)) as ydl:
                        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                        entry = info['entries'][0]
                        path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
                        return path, entry.get('title', 'Music')
                return await asyncio.get_event_loop().run_in_executor(None, run_yt)
            except: continue

    # 2. SoundCloud (быстрее чем YouTube API)
    try:
        def run_sc():
            with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
                info = ydl.extract_info(f"scsearch1:{query}", download=True)
                entry = info['entries'][0]
                path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
                return path, entry.get('title', 'Music')
        return await asyncio.get_event_loop().run_in_executor(None, run_sc)
    except:
        return None

# --- ОБРАБОТЧИКИ ---

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def btn_playlist(message: types.Message):
    songs = get_user_playlist(message.from_user.id)
    if not songs: return await message.answer("📂 Плейлист пуст.")
    
    await message.answer(f"⚡ Начинаю мгновенную загрузку {len(songs)} треков...")
    
    # Запускаем задачи параллельно!
    async def process_single_song(song_query):
        try:
            res = await download_audio(song_query)
            if not res: return
            
            if res[0] == "cache":
                await bot.send_audio(message.chat.id, res[1], caption=f"🎶 {res[2]} (из кэша)", reply_markup=get_song_keyboard(res[2]))
            else:
                path, title = res
                with open(path, 'rb') as f:
                    msg = await bot.send_audio(message.chat.id, f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
                    save_to_cache(song_query, msg.audio.file_id, title)
                if os.path.exists(path): os.remove(path)
        except: pass

    await asyncio.gather(*(process_single_song(s) for s in songs))

@dp.message_handler()
async def handle_message(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]: return await message.answer("Напиши название!")
    
    query = message.text
    status = await message.answer(f"🔎 Ищу...")
    
    res = await download_audio(query)
    if not res:
        return await status.edit_text("❌ Не найдено.")

    if res[0] == "cache":
        await bot.send_audio(message.chat.id, res[1], caption=f"🎶 {res[2]} (Молния ⚡)", reply_markup=get_song_keyboard(res[2]))
        await status.delete()
    else:
        path, title = res
        with open(path, 'rb') as f:
            msg = await bot.send_audio(message.chat.id, f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
            save_to_cache(query, msg.audio.file_id, title)
        if os.path.exists(path): os.remove(path)
        await status.delete()

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)