import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, add_user, log_download, get_stats, get_user_history, add_to_playlist, get_user_playlist

TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

YOUR_ADMIN_ID = 5932714152
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

def get_ydl_opts():
    return {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
    }

async def fast_download(query, prefix="ytsearch1"):
    def run():
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            # Используем поиск по названию
            search_query = f"{prefix}:{query}"
            info = ydl.extract_info(search_query, download=True)
            if 'entries' in info:
                data = info['entries'][0]
            else:
                data = info
            path = ydl.prepare_filename(data).rsplit('.', 1)[0] + ".mp3"
            return path, data.get('title', 'Music')
    return await asyncio.get_event_loop().run_in_executor(None, run)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.reply(f"👋 Бот готов к работе!", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def process_callback(callback_query: types.CallbackQuery):
    action = callback_query.data[:2]
    song_name = callback_query.data[3:]
    if action == "pl":
        add_to_playlist(callback_query.from_user.id, song_name)
        await bot.answer_callback_query(callback_query.id, f"✅ '{song_name}' в плейлисте!")
    else:
        log_download(callback_query.from_user.id, song_name)
        await bot.answer_callback_query(callback_query.id, f"✅ '{song_name}' в скачанных!")

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def btn_playlist(message: types.Message):
    songs = get_user_playlist(message.from_user.id)
    if not songs: 
        return await message.answer("📂 Твой плейлист пока пуст.")
    
    await message.answer(f"📂 Загружаю твой плейлист ({len(songs)} треков)...")
    for s in songs:
        try:
            path, title = await fast_download(s)
            with open(path, 'rb') as f:
                await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except Exception as e:
            await message.answer(f"❌ Не удалось загрузить: {s}")

@dp.message_handler(lambda m: m.text == "📥 Скачанные")
async def btn_history(message: types.Message):
    history = get_user_history(message.from_user.id)
    if not history: 
        return await message.answer("📥 Ты еще ничего не сохранял в скачанные.")
    
    await message.answer("📥 Загружаю последние скачанные...")
    for q in history:
        try:
            path, title = await fast_download(q)
            with open(path, 'rb') as f:
                await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except Exception as e:
            await message.answer(f"❌ Ошибка загрузки: {q}")

@dp.message_handler()
async def search(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]: 
        return await message.answer("Напиши название песни!")
    
    query = message.text
    status = await message.answer(f"🚀 Ищу: **{query}**...")
    try:
        path, title = await fast_download(query)
        with open(path, 'rb') as f:
            await bot.send_audio(message.chat.id, f, caption=f"🎶 **{title}**", reply_markup=get_song_keyboard(title))
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: Не удалось найти '{query}'. Попробуй другое название.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)