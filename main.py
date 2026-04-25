import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# 1. Сначала инициализация
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Путь к нашему встроенному ffmpeg
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

# 2. Функция для создания меню
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = KeyboardButton("🔍 Найти песню")
    btn_downloaded = KeyboardButton("📥 Скачанные")
    btn_wave = KeyboardButton("🌊 Моя волна")
    btn_playlists = KeyboardButton("📂 Мои Плейлисты")
    
    markup.row(btn_search, btn_downloaded)
    markup.row(btn_wave, btn_playlists)
    return markup

# Настройки скачивания
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

# 3. ОБРАБОТЧИКИ КОМАНД

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    welcome_text = (
        f"👋 **Привет, {message.from_user.first_name}!**\n\n"
        "Я твой персональный **Музыкальный Помощник** 🎧\n\n"
        "Здесь ты можешь найти свою любимую песню и слушать её бесплатно или скачать.\n\n"
        "**Мои возможности:**\n"
        "🔍 **Поиск:** Найду любой трек или отрывок.\n"
        "📂 **Плейлисты:** Добавляй свои подборки.\n"
        "🌊 **Моя волна:** Функция рекомендаций, которая тебе понравится! ✨"
    )
    await message.reply(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message_handler(lambda message: message.text == "🔍 Найти песню")
async def search_btn(message: types.Message):
    await message.answer("🎵 Просто **напиши название песни** или слова из неё прямо сюда!")

@dp.message_handler(lambda message: message.text == "📥 Скачанные")
async def downloads_btn(message: types.Message):
    await message.answer("📥 Чтобы сохранить песню в память телефона, нажми на три точки рядом с файлом и выбери **'Сохранить в музыку'**.")

@dp.message_handler(lambda message: message.text == "🌊 Моя волна")
async def wave_btn(message: types.Message):
    await message.answer("🌊 **Моя волна** подбирает музыку специально для тебя! (Функция в процессе настройки 🛠)")

@dp.message_handler(lambda message: message.text == "📂 Мои Плейлисты")
async def playlists_btn(message: types.Message):
    await message.answer("📂 Пришли ссылку на плейлист YouTube или SoundCloud, и я его обработаю!")

# 4. ОБЩИЙ ПОИСК (должен быть в самом конце)
@dp.message_handler()
async def smart_download(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🚀 Ищу для тебя: **{query}**...")

    try:
        # Пробуем YouTube
        file_path, title = await download_logic(query, "ytsearch1")
    except Exception:
        try:
            # Пробуем SoundCloud
            await status_msg.edit_text("🔍 Пробую найти в другой базе...")
            file_path, title = await download_logic(query, "scsearch1")
        except Exception:
            return await status_msg.edit_text("❌ Не удалось найти эту песню. Попробуй другое название.")

    try:
        await status_msg.edit_text("⚡️ Загружаю в Telegram...")
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 **{title}**\nПриятного прослушивания!")
        os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)