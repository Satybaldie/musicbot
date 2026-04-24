import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Берем токен из переменных Railway
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Указываем путь к ffmpeg, который мы скачали в Шаге 1
# Он будет лежать прямо в корневой папке проекта
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_EXE = os.path.join(CURRENT_DIR, "ffmpeg")

ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    # Принудительно тыкаем носом в наш файл
    'ffmpeg_location': FFMPEG_EXE 
}

if not os.path.exists('downloads'):
    os.makedirs('downloads')

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("⚡️ Бот перенастроен! Теперь FFmpeg встроен прямо в папку.\nПопробуй найти песню!")

@dp.message_handler()
async def download_song(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🔍 Ищу и конвертирую: {query}...")

    try:
        # Проверка наличия файла перед скачиванием
        if not os.path.exists(FFMPEG_EXE):
            return await status_msg.edit_text("❌ FFmpeg не найден! Проверь Build Command в Railway.")

        # Поиск через SoundCloud (scsearch) для обхода капчи YouTube
        search_query = f"scsearch1:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)['entries'][0]
            expected_filename = ydl.prepare_filename(info)
            file_path = os.path.splitext(expected_filename)[0] + ".mp3"
            title = info.get('title', 'Music')

        await status_msg.edit_text("📤 Почти готово, отправляю...")
        
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 {title}")
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка:\n{str(e)[:200]}")

if __name__ == '__main__':
    print("Бот запускается...")
    executor.start_polling(dp, skip_updates=True)