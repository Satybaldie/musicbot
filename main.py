import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

# Создаем меню с кнопками
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_wave = KeyboardButton("🌊 Моя волна")
    btn_playlists = KeyboardButton("📂 Мои Плейлисты")
    markup.add(btn_wave, btn_playlists)
    return markup

def get_ydl_opts(query_type="yt"):
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
        'ffmpeg_location': FFMPEG_EXE,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    return opts

async def download_logic(query, search_prefix):
    q_type = "yt" if "yt" in search_prefix else "sc"
    search_query = f"{search_prefix}:{query}"
    loop = asyncio.get_event_loop()
    
    def extract():
        with yt_dlp.YoutubeDL(get_ydl_opts(q_type)) as ydl:
            info = ydl.extract_info(search_query, download=True)['entries'][0]
            expected_filename = ydl.prepare_filename(info)
            file_path = os.path.splitext(expected_filename)[0] + ".mp3"
            return file_path, info.get('title', 'Music')
    return await loop.run_in_executor(None, extract)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    welcome_text = (
        f"👋 **Привет, {message.from_user.first_name}!**\n\n"
        "Я твой персональный **Музыкальный Помощник** 🎧\n\n"
        "**Что я умею:**\n"
        "🔍 **Поиск:** Просто напиши название песни или строчку из неё, и я найду её в лучшем качестве!\n"
        "📥 **Скачивание:** Слушай музыку прямо здесь или сохраняй на устройство бесплатно.\n"
        "📂 **Плейлисты:** Присылай ссылки на свои любимые подборки.\n"
        "🌊 **Моя волна:** Особая функция, которая подберет музыку под твоё настроение! ✨\n\n"
        "✨ *Просто введи название или нажми на кнопку ниже, чтобы начать!*"
    )
    await message.reply(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message_handler(lambda message: message.text == "🌊 Моя волна")
async def wave_info(message: types.Message):
    await message.answer("🌊 **Функция «Моя волна» в разработке!**\nСовсем скоро я смогу предлагать тебе треки, которые точно попадут в твой плейлист. Следи за обновлениями! 😉")

@dp.message_handler(lambda message: message.text == "📂 Мои Плейлисты")
async def playlist_info(message: types.Message):
    await message.answer("📂 **Твои плейлисты:**\nЧтобы добавить плейлист, просто пришли на него ссылку из YouTube или SoundCloud!")

@dp.message_handler()
async def smart_download(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🚀 Ищу для тебя: **{query}**...")

    try:
        # Пытаемся найти в YouTube
        file_path, title = await download_logic(query, "ytsearch1")
    except Exception:
        try:
            # Если YouTube не нашел, идем в SoundCloud
            await status_msg.edit_text("🔍 Пробую найти в дополнительной базе...")
            file_path, title = await download_logic(query, "scsearch1")
        except Exception:
            return await status_msg.edit_text("❌ К сожалению, я не смог найти эту песню. Попробуй уточнить название!")

    try:
        await status_msg.edit_text("⚡️ Почти готово! Загружаю в Telegram...")
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 **{title}**\nПриятного прослушивания! ✨")
        os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке файла: {e}")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)