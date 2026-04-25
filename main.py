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
    # Ограничиваем длину текста для callback_data (макс 64 байта)
    clean_title = title[:30]
    markup.add(
        InlineKeyboardButton("➕ В плейлист", callback_data=f"pl_{clean_title}"),
        InlineKeyboardButton("📥 В скачанные", callback_data=f"dl_{clean_title}")
    )
    return markup

def get_ydl_opts():
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    }
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
    return opts

async def fast_download(query, prefix="ytsearch1"):
    def run():
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(f"{prefix}:{query}", download=True)['entries'][0]
            path = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"
            return path, info.get('title', 'Music')
    return await asyncio.get_event_loop().run_in_executor(None, run)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.reply(f"👋 Привет! Я твой Музыкальный Менеджер 🎧", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith(('pl_', 'dl_')))
async def process_callback(callback_query: types.CallbackQuery):
    action = callback_query.data[:2]
    song_name = callback_query.data[3:]
    if action == "pl":
        add_to_playlist(callback_query.from_user.id, song_name)
        await bot.answer_callback_query(callback_query.id, "✅ Добавлено в Плейлисты!")
    else:
        log_download(callback_query.from_user.id, song_name)
        await bot.answer_callback_query(callback_query.id, "✅ Добавлено в Скачанные!")

@dp.message_handler(lambda m: m.text == "📂 Мои Плейлисты")
async def btn_playlist(message: types.Message):
    songs = get_user_playlist(message.from_user.id)
    if not songs: return await message.answer("📂 Плейлист пуст.")
    await message.answer("📂 Твой Плейлист:")
    for s in songs:
        try:
            path, title = await fast_download(s)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler(lambda m: m.text == "📥 Скачанные")
async def btn_history(message: types.Message):
    history = get_user_history(message.from_user.id)
    if not history: return await message.answer("📥 История пуста.")
    await message.answer("📥 Твои последние скачанные:")
    for q in history:
        try:
            path, title = await fast_download(q)
            with open(path, 'rb') as f: await message.answer_audio(f, caption=f"🎶 {title}")
            if os.path.exists(path): os.remove(path)
        except: continue

@dp.message_handler()
async def search(message: types.Message):
    if message.text in ["🔍 Найти песню", "🌊 Моя волна"]: return await message.answer("Напиши название песни!")
    query = message.text
    status = await message.answer(f"🚀 Ищу: **{query}**...")
    try:
        path, title = await fast_download(query)
        with open(path, 'rb') as f:
            await message.answer_audio(f, caption=f"🎶 **{title}**", reply_markup=get_song_keyboard(title))
        if os.path.exists(path): os.remove(path)
        await status.delete()
    except:
        try:
            await status.edit_text("🔍 Пробую резервный поиск...")
            path, title = await fast_download(query, "scsearch1")
            with open(path, 'rb') as f:
                await message.answer_audio(f, caption=f"🎶 **{title}**", reply_markup=get_song_keyboard(title))
            if os.path.exists(path): os.remove(path)
            await status.delete()
        except:
            await status.edit_text("❌ Не нашел. Попробуй другое название.")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)