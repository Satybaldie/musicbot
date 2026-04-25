import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Импортируем функции базы данных
from database import init_db, add_user, log_download, get_stats

# 1. Инициализация
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Твой ID для админ-прав
YOUR_ADMIN_ID = 5932714152

# Инициализируем БД при старте
init_db()

# Путь к ffmpeg
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

# 2. Главное меню
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = KeyboardButton("🔍 Найти песню")
    btn_downloaded = KeyboardButton("📥 Скачанные")
    btn_wave = KeyboardButton("🌊 Моя волна")
    btn_playlists = KeyboardButton("📂 Мои Плейлисты")
    
    markup.row(btn_search, btn_downloaded)
    markup.row(btn_wave, btn_playlists)
    return markup

# Опции скачивания
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

# 3. Обработчики команд

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    # Добавляем пользователя в базу
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
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

# Команда статистики (только для тебя)
@dp.message_handler(commands=['admin'])
async def admin_stats(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        u_count, d_count = get_stats()
        await message.answer(f"📊 **Статистика бота:**\n\n👤 Юзеров: {u_count}\n🎵 Скачано песен: {d_count}")
    else:
        await message.answer("❌ У вас нет прав администратора.")

# Команда рассылки (только для тебя)
@dp.message_handler(commands=['send'])
async def broadcast(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        broadcast_text = message.get_args()
        if not broadcast_text:
            return await message.answer("❌ Введите текст после команды. Пример: `/send Привет всем!`")
        
        import sqlite3
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        conn.close()
        
        count = 0
        await message.answer(f"📢 Начинаю рассылку на {len(users)} чел...")
        for user in users:
            try:
                await bot.send_message(user[0], broadcast_text)
                count += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await message.answer(f"✅ Рассылка завершена! Получили: {count} чел.")
    else:
        await message.answer("❌ Доступ запрещен.")

# Обработка кнопок меню
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

# 4. Общий поиск (основная логика)
@dp.message_handler()
async def smart_download(message: types.Message):
    query = message.text
    log_download(message.from_user.id, query)
    
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
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    executor.start_polling(dp, skip_updates=True)