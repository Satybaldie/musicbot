import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Путь к нашему "встроенному" ffmpeg
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

def get_ydl_opts(query_type="sc"):
    """
    query_type: "sc" для SoundCloud, "yt" для YouTube
    """
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'ffmpeg_location': FFMPEG_EXE
    }
    
    # Если ищем в YouTube, добавляем имитацию браузера, чтобы не забанили
    if query_type == "yt":
        opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    
    return opts

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("🎵 **Музыкальный бот 2.0**\nЯ ищу в SoundCloud и YouTube. Просто пришли название или слова из песни!")

@dp.message_handler()
async def smart_download(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🔍 Ищу «{query}»...")

    # Шаг 1: Пробуем SoundCloud
    try:
        file_path, title = await download_logic(query, "scsearch1")
    except Exception:
        # Шаг 2: Если SoundCloud подвел, пробуем YouTube
        try:
            await status_msg.edit_text(f"🔎 В SoundCloud не нашлось, пробую YouTube...")
            file_path, title = await download_logic(query, "ytsearch1")
        except Exception as e:
            return await status_msg.edit_text(f"❌ Ничего не нашлось даже в YouTube.\nОшибка: {str(e)[:50]}")

    # Шаг 3: Отправка
    try:
        await status_msg.edit_text("📤 Отправляю...")
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 {title}")
        os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await message.answer(f" Ошибка при отправке: {e}")

async def download_logic(query, search_prefix):
    search_query = f"{search_prefix}:{query}"
    q_type = "yt" if "yt" in search_prefix else "sc"
    
    with yt_dlp.YoutubeDL(get_ydl_opts(q_type)) as ydl:
        info = ydl.extract_info(search_query, download=True)['entries'][0]
        expected_filename = ydl.prepare_filename(info)
        file_path = os.path.splitext(expected_filename)[0] + ".mp3"
        return file_path, info.get('title', 'Music')

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)