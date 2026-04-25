import os
import asyncio
import yt_dlp
import requests
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
COOKIE_FILES = ['cookies1.txt', 'cookies2.txt', 'cookies3.txt']

# --- ГЕНЕРАЦИЯ КНОПОК ---

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔍 Найти песню"), KeyboardButton("📥 Скачанные"))
    markup.row(KeyboardButton("🌊 Моя волна"), KeyboardButton("📂 Мои Плейлисты"))
    return markup

def get_song_keyboard(title):
    markup = InlineKeyboardMarkup()
    # Обрезаем название для callback_data (лимит 64 байта)
    clean_title = title[:30]
    markup.add(
        InlineKeyboardButton("➕ В плейлист", callback_data=f"pl_{clean_title}"),
        InlineKeyboardButton("📥 В скачанные", callback_data=f"dl_{clean_title}")
    )
    return markup

# --- ЛОГИКА СКАЧИВАНИЯ ---

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
    # 1. Попытка через YouTube с ротацией 3-х КУКИ
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
            except:
                continue

    # 2. Попытка через Google API (без куки)
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={GOOGLE_API_KEY}&maxResults=1"
        api_res = requests.get(url, timeout=5).json()
        if 'items' in api_res and len(api_res['items']) > 0:
            v_id = api_res['items'][0]['id']['videoId']
            v_link = f"https://www.youtube.com/watch?v={v_id}"
            def run_api():
                with yt_dlp.YoutubeDL(get_ydl_opts(None)) as ydl:
                    info = ydl.extract_info(v_link, download=True)
                    path = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"
                    return path, info.get('title', 'Music')
            return await asyncio.get_event_loop().run_in_executor(None, run_api)
    except:
        pass

    # 3. Финальная попытка через SoundCloud
    def run_sc():
        with yt_dlp.YoutubeDL(get_ydl_opts(None)) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            entry = info['entries'][0]
            path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
            return path, entry.get('title', 'Music')
    return await asyncio.get_event_loop().run_in_executor(None, run_sc)

# --- ОБРАБОТЧИКИ ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    found_cookies = len([f for f in COOKIE_FILES if os.path.exists(f)])
    await message.reply(f"🎧 Бот готов!\nНайдено куки: {found_cookies}/3\nМетоды: YouTube(3x) -> API -> SoundCloud", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def process_callback(call: types.CallbackQuery):
    action, song_name = call.data[:2], call.data[3:]
    if action == "pl":
        add_to_playlist(call.from_user.id, song_name)
        await call.answer("🎶 Добавлено в плейлист!")
    else:
        log_download(call.from_user.id, song_name)
        await call.answer("📥 Добавлено в скачанные!")

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def btn_playlist(message: types.Message):
    songs = get_user_playlist(message.from_user.id)
    if not songs: return await message.answer("📂 Плейлист пуст.")
    await message.answer("⌛ Загружаю ваш плейлист...")
    for s in songs:
        try:
            path, title = await download_audio(s)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler(lambda m: m.text == "📥 Скачанные")
async def btn_history(message: types.Message):
    history = get_user_history(message.from_user.id)
    if not history: return await message.answer("📥 История пуста.")
    await message.answer("⌛ Загружаю историю...")
    for q in history:
        try:
            path, title = await download_audio(q)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}", reply_markup=get_song_keyboard(title))
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler()
async def handle_message(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]:
        return await message.answer("Введите название песни:", reply_markup=get_main_menu())
    
    status = await message.answer(f"🔎 Ищу: **{message.text}**...")
    try:
        path, title = await download_audio(message.text)
        with open(path, 'rb') as f:
            await bot.send_audio(message.chat.id, f, caption=f"🎶 **{title}**", reply_markup=get_song_keyboard(title))
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        await status.edit_text("❌ Песня не найдена ни одним из способов.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)