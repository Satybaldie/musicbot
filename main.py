import os
import asyncio
import yt_dlp
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_user, log_download, get_stats, get_user_history, add_to_playlist, get_user_playlist

# ТОКЕНЫ И НАСТРОЙКИ
TOKEN = os.getenv('BOT_TOKEN')
# Твой проверенный API ключ
GOOGLE_API_KEY = "AIzaSyBPqLNBRJAXxv4HyMO-WMFMns95YccOB2c"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
init_db()

# Путь к ffmpeg для Railway
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔍 Найти песню"), KeyboardButton("📥 Скачанные"))
    markup.row(KeyboardButton("🌊 Моя волна"), KeyboardButton("📂 Мои Плейлисты"))
    return markup

def get_song_keyboard(title):
    markup = InlineKeyboardMarkup()
    # Обрезаем заголовок для корректной работы кнопок
    clean_title = title[:30]
    markup.add(
        InlineKeyboardButton("➕ В плейлист", callback_data=f"pl_{clean_title}"),
        InlineKeyboardButton("📥 В скачанные", callback_data=f"dl_{clean_title}")
    )
    return markup

# Официальный поиск ссылки через Google API
def get_video_url(query):
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={GOOGLE_API_KEY}&maxResults=1"
        r = requests.get(url, timeout=10)
        data = r.json()
        if 'items' in data and len(data['items']) > 0:
            v_id = data['items'][0]['id']['videoId']
            return f"https://www.youtube.com/watch?v={v_id}"
    except Exception as e:
        print(f"Search error: {e}")
    return None

async def download_audio(query):
    # Сначала ищем официальную ссылку
    link = await asyncio.get_event_loop().run_in_executor(None, get_video_url, query)
    # Если Google не ответил, используем встроенный поиск yt-dlp
    final_query = link if link else f"ytsearch1:{query}"

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
    }

    def run_dl():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(final_query, download=True)
            entry = info['entries'][0] if 'entries' in info else info
            path = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
            return path, entry.get('title', 'Music')
            
    return await asyncio.get_event_loop().run_in_executor(None, run_dl)

# ОБРАБОТКА СООБЩЕНИЙ
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("🚀 Бот запущен через Google API! Напиши название песни.", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def callbacks(call: types.CallbackQuery):
    action, name = call.data[:2], call.data[3:]
    if action == "pl":
        add_to_playlist(call.from_user.id, name)
        await call.answer("🎵 Добавлено в Плейлисты!")
    else:
        log_download(call.from_user.id, name)
        await call.answer("📥 Добавлено в Скачанные!")

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def show_playlist(message: types.Message):
    songs = get_user_playlist(message.from_user.id)
    if not songs: return await message.answer("📂 Плейлист пуст.")
    await message.answer("⌛ Загружаю твой плейлист...")
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
    await message.answer("⌛ Загружаю последние треки...")
    for s in songs:
        try:
            path, title = await download_audio(s)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler()
async def search_song(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]: return await message.answer("Просто напиши название!")
    
    status = await message.answer(f"🔎 Ищу: **{message.text}**...")
    try:
        path, title = await download_audio(message.text)
        with open(path, 'rb') as f:
            await message.answer_audio(f, caption=f"🎶 **{title}**", reply_markup=get_song_keyboard(title))
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except Exception as e:
        await status.edit_text("❌ Не удалось найти или скачать. Попробуй другое название.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)