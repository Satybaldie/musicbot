import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import yt_dlp

# Берем токен из BotFather через переменные Railway
TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Папка для временного хранения песен
if not os.path.exists('downloads'):
    os.makedirs('downloads')

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Привет! Я твой музыкальный бот. Пришли мне название песни или ссылку, и я её найду!")

@dp.message_handler()
async def search_and_send(message: types.Message):
    search_query = message.text
    sent_msg = await message.answer(f"🔍 Ищу «{search_query}»...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Ищем первую подходящую песню
            info = ydl.extract_info(f"ytsearch1:{search_query}", download=True)['entries'][0]
            file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            title = info.get('title', 'Music')

        await sent_msg.edit_text("📤 Отправляю файл...")
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 {title}")
        
        # Удаляем файл после отправки, чтобы не забивать место
        os.remove(file_path)
        await sent_msg.delete()

    except Exception as e:
        await sent_msg.edit_text(f"❌ Ошибка: {str(e)}")

if name == 'main':
    executor.start_polling(dp, skip_updates=True)