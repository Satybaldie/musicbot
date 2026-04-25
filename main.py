import os
import asyncio
import yt_dlp
import requests
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_user, log_download, get_user_history, add_to_playlist, get_user_playlist

# НАСТРОЙКИ
TOKEN = os.getenv('BOT_TOKEN')
GOOGLE_API_KEY = "AIzaSyBPqLNBRJAXxv4HyMO-WMFMns95YccOB2c"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

# Список твоих файлов куки
COOKIE_FILES = ['cookies1.txt', 'cookies2.txt', 'cookies3.txt']

def get_ydl_opts(cookie_file=None):
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
    }
    if cookie_file and os.path.exists(cookie_file):
        opts['cookiefile'] = cookie_file
    return opts

async def download_audio(query):
    # --- ЭТАП 1: Пробуем YouTube с разными куки ---
    for c_file in COOKIE_FILES:
        if os.path.exists(c_file):
            try:
                def run_dl_yt():
                    with yt_dlp.YoutubeDL(get_ydl_opts(c_file)) as ydl:
                        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                        entry = info['entries'][0]
                        path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
                        return path, entry.get('title', 'Music')
                return await asyncio.get_event_loop().run_in_executor(None, run_dl_yt)
            except Exception as e:
                print(f"Ошибка с {c_file}: {e}")
                continue # Если этот файл куки не сработал, пробуем следующий

    # --- ЭТАП 2: Если куки не помогли, пробуем Google API (IP) ---
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={GOOGLE_API_KEY}&maxResults=1"
        api_data = requests.get(url, timeout=5).json()
        if 'items' in api_data:
            v_id = api_data['items'][0]['id']['videoId']
            link = f"https://www.youtube.com/watch?v={v_id}"
            def run_dl_api():
                with yt_dlp.YoutubeDL(get_ydl_opts(None)) as ydl:
                    info = ydl.extract_info(link, download=True)
                    path = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"
                    return path, info.get('title', 'Music')
            return await asyncio.get_event_loop().run_in_executor(None, run_dl_api)
    except:
        pass

    # --- ЭТАП 3: Финальный шанс - SoundCloud ---
    try:
        def run_dl_sc():
            with yt_dlp.YoutubeDL(get_ydl_opts(None)) as ydl:
                info = ydl.extract_info(f"scsearch1:{query}", download=True)
                entry = info['entries'][0]
                path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
                return path, entry.get('title', 'Music')
        return await asyncio.get_event_loop().run_in_executor(None, run_dl_sc)
    except Exception as e:
        raise e

# --- ОБРАБОТЧИКИ (без изменений, просто вызываем download_audio) ---

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    found = [f for f in COOKIE_FILES if os.path.exists(f)]
    await message.answer(f"🚀 Бот запущен!\nНайдено куки-файлов: {len(found)} из 3", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🔍 Найти песню"))

@dp.message_handler()
async def search_song(message: types.Message):
    if message.text == "🔍 Найти песню": return await message.answer("Напиши название!")
    status = await message.answer(f"🔎 Ищу через 3 куки и резервные каналы...")
    try:
        path, title = await download_audio(message.text)
        with open(path, 'rb') as f:
            await message.answer_audio(f, caption=f"🎶 **{title}**")
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        await status.edit_text("❌ Песня не найдена ни одним из способов.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)