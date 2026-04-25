import os
import asyncio
import yt_dlp
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_user, log_download, get_stats, get_user_history, add_to_playlist, get_user_playlist

# НАСТРОЙКИ
TOKEN = os.getenv('BOT_TOKEN')
GOOGLE_API_KEY = "AIzaSyBPqLNBRJAXxv4HyMO-WMFMns95YccOB2c"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

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

# Резервный поиск через Google API
def google_search(query):
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={GOOGLE_API_KEY}&maxResults=1"
        r = requests.get(url, timeout=5)
        data = r.json()
        if 'items' in data and len(data['items']) > 0:
            return f"https://www.youtube.com/watch?v={data['items'][0]['id']['videoId']}"
    except:
        return None
    return None

async def download_audio(query):
    # Очередность поиска: 1. Google API, 2. SoundCloud (самый стабильный), 3. YouTube Search
    link = await asyncio.get_event_loop().run_in_executor(None, google_search, query)
    
    # Список стратегий поиска
    search_strategies = []
    if link:
        search_strategies.append(link) # Прямая ссылка от Google
    search_strategies.append(f"scsearch1:{query}") # SoundCloud
    search_strategies.append(f"ytsearch1:{query}") # Обычный поиск YouTube

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
    }

    last_exc = None
    for target in search_strategies:
        try:
            def run_dl():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target, download=True)
                    entry = info['entries'][0] if 'entries' in info else info
                    path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
                    return path, entry.get('title', 'Music')
            return await asyncio.get_event_loop().run_in_executor(None, run_dl)
        except Exception as e:
            last_exc = e
            continue # Если не вышло, пробуем следующий источник
    
    raise last_exc

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("🎧 Бот готов! Поиск усилен резервными каналами.", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def callbacks(call: types.CallbackQuery):
    action, name = call.data[:2], call.data[3:]
    if action == "pl":
        add_to_playlist(call.from_user.id, name)
        await call.answer("➕ Добавлено в Плейлисты!")
    else:
        log_download(call.from_user.id, name)
        await call.answer("📥 Добавлено в Скачанные!")

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def show_playlist(message: types.Message):
    songs = get_user_playlist(message.from_user.id)
    if not songs: return await message.answer("📂 Плейлист пуст.")
    await message.answer("📂 Загружаю песни...")
    for s in songs:
        try:
            path, title = await download_audio(s)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler(lambda m: m.text == "📥 Скачанные")
async def show_history(message: types.Message):
    songs = get_user_history(message.from_user.id)
    if not songs: return await message.answer("📥 История пуста.")
    await message.answer("📥 Загружаю историю...")
    for s in songs:
        try:
            path, title = await download_audio(s)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler()
async def search_song(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]: return await message.answer("Напиши название!")
    
    status = await message.answer(f"🔎 Ищу: **{message.text}**...")
    try:
        path, title = await download_audio(message.text)
        with open(path, 'rb') as f:
            await message.answer_audio(f, caption=f"🎶 **{title}**", reply_markup=get_song_keyboard(title))
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        await status.edit_text("❌ Не удалось найти аудио даже через резервные каналы. Попробуй другое название.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)