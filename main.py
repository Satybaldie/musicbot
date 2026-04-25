import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Токен берем из переменных Railway
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Путь к нашему встроенному ffmpeg
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

def get_ydl_opts(query_type="yt"):
    """
    query_type: "yt" для YouTube, "sc" для SoundCloud
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
    
    # Настройки для YouTube, чтобы он думал, что мы обычный человек через браузер
    if query_type == "yt":
        opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        opts['referer'] = 'https://www.google.com/'
    
    return opts

async def download_logic(query, search_prefix):
    q_type = "yt" if "yt" in search_prefix else "sc"
    search_query = f"{search_prefix}:{query}"
    
    # Используем асинхронный запуск в потоке, чтобы бот не зависал во время скачивания
    loop = asyncio.get_event_loop()
    
    def extract():
        with yt_dlp.YoutubeDL(get_ydl_opts(q_type)) as ydl:
            info = ydl.extract_info(search_query, download=True)['entries'][0]
            expected_filename = ydl.prepare_filename(info)
            # yt-dlp меняет расширение на .mp3 после обработки
            file_path = os.path.splitext(expected_filename)[0] + ".mp3"
            return file_path, info.get('title', 'Music')

    return await loop.run_in_executor(None, extract)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("🚀 **Бот-меломан запущен!**\n\nСначала ищу в YouTube, а если там не выйдет — пойду в SoundCloud. Просто напиши название или слова из песни!")

@dp.message_handler()
async def smart_download(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🔍 Ищу «{query}» в YouTube...")

    # ШАГ 1: Пробуем YouTube
    try:
        file_path, title = await download_logic(query, "ytsearch1")
    except Exception as e:
        # ШАГ 2: Если YouTube выдал ошибку (например, бан IP), пробуем SoundCloud
        print(f"Ошибка YouTube: {e}")
        try:
            await status_msg.edit_text(f"⚠️ В YouTube не вышло, ищу в SoundCloud...")
            file_path, title = await download_logic(query, "scsearch1")
        except Exception as sc_e:
            print(f"Ошибка SoundCloud: {sc_e}")
            return await status_msg.edit_text(f"❌ Песня не найдена ни в одном источнике.")

    # ШАГ 3: Отправка готового файла
    try:
        await status_msg.edit_text("📤 Почти готово, отправляю в Telegram...")
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 {title}")
        
        # Удаляем файл после отправки
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке аудио: {e}")

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    print("Бот в сети!")
    executor.start_polling(dp, skip_updates=True)