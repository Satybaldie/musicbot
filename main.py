import os
import asyncio
import yt_dlp
import requests
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_user, log_download, get_user_history, add_to_playlist, get_user_playlist

# ТОКЕНЫ
TOKEN = os.getenv('BOT_TOKEN')
GOOGLE_API_KEY = "AIzaSyBPqLNBRJAXxv4HyMO-WMFMns95YccOB2c"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")
COOKIE_FILES = ['cookies1.txt', 'cookies2.txt', 'cookies3.txt']

# --- КЭШ И КНОПКИ ---

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

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔍 Найти песню"), KeyboardButton("📥 Скачанные"))
    markup.row(KeyboardButton("🌊 Моя волна"), KeyboardButton("📂 Мои Плейлисты"))
    return markup

def get_song_keyboard(title):
    markup = InlineKeyboardMarkup()
    # Обрезаем название до 25 символов для стабильности кнопок
    safe_title = title[:25].strip()
    markup.add(
        InlineKeyboardButton("➕ В плейлист", callback_data=f"pl_{safe_title}"),
        InlineKeyboardButton("📥 В скачанные", callback_data=f"dl_{safe_title}")
    )
    return markup

# --- СКАЧИВАНИЕ ---

def get_ydl_opts(cookie_file=None):
    return {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
        'cookiefile': cookie_file if cookie_file and os.path.exists(cookie_file) else None
    }

async def download_audio(query):
    # 0. Проверка кэша
    cached = get_from_cache(query)
    if cached: return "cache", cached[0], cached[1]

    # 1. Попытка через куки (1, 2, 3)
    for c_file in COOKIE_FILES:
        if os.path.exists(c_file):
            try:
                def run_yt():
                    with yt_dlp.YoutubeDL(get_ydl_opts(c_file)) as ydl:
                        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                        entry = info['entries'][0]
                        return ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3", entry.get('title', 'Music')
                return await asyncio.get_event_loop().run_in_executor(None, run_yt)
            except: continue

    # 2. Попытка через Google API
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={GOOGLE_API_KEY}&maxResults=1"
        v_id = requests.get(url, timeout=5).json()['items'][0]['id']['videoId']
        def run_api():
            with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={v_id}", download=True)
                return ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3", info.get('title', 'Music')
        return await asyncio.get_event_loop().run_in_executor(None, run_api)
    except: pass

    # 3. SoundCloud
    def run_sc():
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            entry = info['entries'][0]
            return ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3", entry.get('title', 'Music')
    return await asyncio.get_event_loop().run_in_executor(None, run_sc)

# --- ОБРАБОТЧИКИ ---

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("👋 Привет! Я готов к работе.\n\nОчередь поиска настроена: 3x Cookies -> API -> SoundCloud.", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def callbacks(call: types.CallbackQuery):
    action, name = call.data[:2], call.data[3:]
    if action == "pl":
        add_to_playlist(call.from_user.id, name)
        await call.answer(f"➕ {name} в плейлисте")
    else:
        log_download(call.from_user.id, name)
        await call.answer(f"📥 {name} в истории")

@dp.message_handler(lambda m: m.text == "📥 Скачанные")
async def show_history(message: types.Message):
    h = get_user_history(message.from_user.id)
    if not h: return await message.answer("📥 История пуста.")
    await message.answer("⌛ Достаю треки из кэша...")
    for q in h:
        res = await download_audio(q)
        if res:
            if res[0] == "cache":
                await bot.send_audio(message.chat.id, res[1], caption=f"🎶 {res[2]}", reply_markup=get_song_keyboard(res[2]))
            else:
                path, title = res
                with open(path, 'rb') as f:
                    msg = await bot.send_audio(message.chat.id, f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
                    save_to_cache(q, msg.audio.file_id, title)
                if os.path.exists(path): os.remove(path)

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def show_playlist(message: types.Message):
    p = get_user_playlist(message.from_user.id)
    if not p: return await message.answer("📂 Плейлист пуст.")
    await message.answer("⌛ Загружаю ваш плейлист...")
    for s in p:
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

@dp.message_handler()
async def search(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]: return await message.answer("Напиши название!")
    status = await message.answer(f"🔎 Ищу: **{message.text}**...")
    try:
        res = await download_audio(message.text)
        if res[0] == "cache":
            await bot.send_audio(message.chat.id, res[1], caption=f"🎶 {res[2]} ⚡", reply_markup=get_song_keyboard(res[2]))
        else:
            path, title = res
            with open(path, 'rb') as f:
                msg = await bot.send_audio(message.chat.id, f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
                save_to_cache(message.text, msg.audio.file_id, title)
            if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        await status.edit_text("❌ Не удалось найти песню.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)