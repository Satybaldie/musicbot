import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Токен берем из переменных Railway (BOT_TOKEN)
TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Настройки скачивания (теперь приоритет на SoundCloud)
ydl_opts = {
    'format': 'bestaudio/best',
    'keepvideo': False,
    'noplaylist': True,
    'quiet': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
}

# Создаем папку для музыки, если её нет
if not os.path.exists('downloads'):
    os.makedirs('downloads')

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("🎵 **Бот готов к работе!**\n\nПросто напиши название песни или исполнителя, и я пришлю тебе аудиофайл (поиск через SoundCloud).")

@dp.message_handler()
async def download_song(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🔍 Ищу «{query}» в SoundCloud...")

    try:
        # scsearch1 — ищет одну самую подходящую песню в SoundCloud
        search_query = f"scsearch1:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)['entries'][0]
            # Получаем путь к скачанному файлу
            expected_filename = ydl.prepare_filename(info)
            # После обработки расширение сменится на .mp3
            file_path = os.path.splitext(expected_filename)[0] + ".mp3"
            title = info.get('title', 'Music')
            performer = info.get('uploader', 'SoundCloud')

        await status_msg.edit_text("📤 Отправляю файл...")
        
        with open(file_path, 'rb') as audio:
            await message.answer_audio(
                audio, 
                caption=f"🎶 {title}",
                performer=performer,
                title=title
            )
        
        # Удаляем файл, чтобы не забивать память сервера
        if os.path.exists(file_path):
            os.remove(file_path)
            
        await status_msg.delete()

    except Exception as e:
        error_text = str(e)
        # Если вдруг SoundCloud не нашел, можно попробовать YouTube как запасной вариант
        await status_msg.edit_text(f"❌ Не удалось найти или скачать.\nОшибка: {error_text[:100]}...")

if __name__ == '__main__':
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)