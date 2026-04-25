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

# Функция для поиска через Google API (Твой 2-й пункт)
def google_search_api(query):
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={GOOGLE_API_KEY}&maxResults=1"
        r = requests.get(url, timeout=5)
        data = r.json()
        if 'items' in data and len(data['items']) > 0:
            return f"https://www.youtube.com/watch?v={data['items'][0]['id']['videoId']}"
    except:
        return None
    return None

# Настройки скачивания (ydl_opts)
def get_ydl_opts(use_cookies=True):
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
    }
    # ПУНКТ 1: Используем куки только если разрешено и файл существует
    if use_cookies and os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
    return opts

async def download_audio(query):
    # ОПРЕДЕЛЯЕМ ТВОЮ ОЧЕРЕДЬ:
    
    # 1. Прямой поиск в YouTube через куки
    # 2. Поиск через Google API (IP) без куки
    # 3. SoundCloud (как финальный вариант)
    
    # Сначала узнаем ссылку от Google для 2-го шага
    api_link = await asyncio.get_event_loop().run_in_executor(None, google_search_api, query)
    
    # Составляем список стратегий (Тип поиска, Нужно ли куки, Строка поиска)
    strategies = [
        ("YouTube (Cookies)", True, f"ytsearch1:{query}"), # Шаг 1
        ("Google API (IP)", False, api_link if api_link else f"ytsearch1:{query}"), # Шаг 2
        ("SoundCloud", False, f"scsearch1:{query}") # Шаг 3
    ]

    last_error = None
    for name, use_cookies, target in strategies:
        try:
            print(f"Попытка через: {name}")
            def run_dl():
                with yt_dlp.YoutubeDL(get_ydl_opts(use_cookies)) as ydl:
                    info = ydl.extract_info(target, download=True)
                    entry = info['entries'][0] if 'entries' in info else info
                    path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
                    return path, entry.get('title', 'Music')
            return await asyncio.get_event_loop().run_in_executor(None, run_dl)
        except Exception as e:
            last_error = e
            print(f"Ошибка в {name}: {e}")
            continue # Переходим к следующему пункту в очереди
    
    raise last_error

# --- ОБРАБОТЧИКИ (Остаются без изменений) ---

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    has_cookies = "✅ Cookies.txt найден" if os.path.exists('cookies.txt') else "⚠️ Cookies.txt отсутствует"
    await message.answer(f"🚀 Бот настроен!\n\nОчередь:\n1. YouTube (Cookies)\n2. Google API (IP)\n3. SoundCloud\n\nСтатус: {has_cookies}", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def callbacks(call: types.CallbackQuery):
    action, name = call.data[:2], call.data[3:]
    if action == "pl":
        add_to_playlist(call.from_user.id, name)
        await call.answer("🎵 В плейлисте!")
    else:
        log_download(call.from_user.id, name)
        await call.answer("📥 В скачанных!")

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def show_playlist(message: types.Message):
    songs = get_user_playlist(message.from_user.id)
    if not songs: return await message.answer("📂 Плейлист пуст.")
    await message.answer("📂 Загружаю плейлист по новой очереди...")
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
    await message.answer("📥 Загружаю последние треки...")
    for s in songs:
        try:
            path, title = await download_audio(s)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler()
async def search_song(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]: return await message.answer("Напиши название!")
    
    status = await message.answer(f"🔎 Ищу (Шаг 1: YouTube + Cookies)...")
    try:
        path, title = await download_audio(message.text)
        with open(path, 'rb') as f:
            await message.answer_audio(f, caption=f"🎶 **{title}**", reply_markup=get_song_keyboard(title))
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        await status.edit_text("❌ Песня не найдена ни одним из 3 способов.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)