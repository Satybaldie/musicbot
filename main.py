import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Импортируем функции из database.py
from database import init_db, add_user, log_download, get_stats, get_user_history

# 1. Настройка
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Твой ID администратора
YOUR_ADMIN_ID = 5932714152

# Инициализация базы данных при запуске
init_db()

# Путь к ffmpeg
FFMPEG_EXE = os.path.join(os.getcwd(), "ffmpeg")

# 2. Создание главного меню
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = KeyboardButton("🔍 Найти песню")
    btn_downloaded = KeyboardButton("📥 Скачанные")
    btn_wave = KeyboardButton("🌊 Моя волна")
    btn_playlists = KeyboardButton("📂 Мои Плейлисты")
    
    markup.row(btn_search, btn_downloaded)
    markup.row(btn_wave, btn_playlists)
    return markup

# Настройки для скачивания через yt-dlp
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

# 3. Обработчики команд и кнопок

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    # Регистрируем пользователя
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    welcome_text = (
        f"👋 **Привет, {message.from_user.first_name}!**\n\n"
        "Я твой персональный **Музыкальный Помощник** 🎧\n\n"
        "Здесь ты можешь найти свою любимую песню и слушать её бесплатно или скачать.\n\n"
        "**Мои возможности:**\n"
        "🔍 **Поиск:** Найду любой трек по названию или словам.\n"
        "📥 **Скачанные:** Твоя персональная история поисков.\n"
        "🌊 **Моя волна:** Рекомендации специально для тебя! ✨"
    )
    await message.reply(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message_handler(commands=['admin'])
async def admin_stats(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        u_count, d_count = get_stats()
        await message.answer(f"📊 **Статистика бота:**\n\n👤 Пользователей: {u_count}\n🎵 Всего скачиваний: {d_count}")
    else:
        await message.answer("❌ У вас нет прав доступа к этой команде.")

@dp.message_handler(commands=['send'])
async def broadcast(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        broadcast_text = message.get_args()
        if not broadcast_text:
            return await message.answer("❌ Введите текст рассылки: `/send Привет!`", parse_mode="Markdown")
        
        import sqlite3
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        conn.close()
        
        count = 0
        status = await message.answer(f"📢 Рассылка на {len(users)} чел. началась...")
        for user in users:
            try:
                await bot.send_message(user[0], broadcast_text)
                count += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await status.edit_text(f"✅ Рассылка завершена!\nПолучили: {count} пользователей.")
    else:
        await message.answer("❌ Доступ запрещен.")

@dp.message_handler(lambda message: message.text == "📥 Скачанные")
async def downloaded_history(message: types.Message):
    history = get_user_history(message.from_user.id)
    if history:
        text = "📥 **Твои последние запросы:**\n\n"
        for item in history:
            text += f"• `{item}`\n"
        text += "\n_Нажми на название, чтобы скопировать его, и отправь мне для повторного поиска!_"
    else:
        text = "📥 В твоей истории пока пусто. Найди свою первую песню! 😉"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda message: message.text == "🔍 Найти песню")
async def search_help(message: types.Message):
    await message.answer("🎵 Просто **напиши название песни** или строчку из неё прямо сюда!")

@dp.message_handler(lambda message: message.text == "🌊 Моя волна")
async def wave_info(message: types.Message):
    await message.answer("🌊 **Моя волна** подбирает музыку под твой вкус! (Функция в процессе настройки 🛠)")

@dp.message_handler(lambda message: message.text == "📂 Мои Плейлисты")
async def playlists_info(message: types.Message):
    await message.answer("📂 Пришли ссылку на плейлист (YouTube/SoundCloud), и я скачаю его целиком!")

# 4. Логика поиска и скачивания
@dp.message_handler()
async def main_search(message: types.Message):
    query = message.text
    log_download(message.from_user.id, query) # Сохраняем запрос в историю
    
    status_msg = await message.answer(f"🚀 Ищу: **{query}**...")
    
    try:
        # 1-я попытка: YouTube
        file_path, title = await download_logic(query, "ytsearch1")
    except Exception:
        try:
            # 2-я попытка: SoundCloud
            await status_msg.edit_text("🔍 Ищу в резервном источнике...")
            file_path, title = await download_logic(query, "scsearch1")
        except Exception:
            return await status_msg.edit_text("❌ Не удалось найти песню. Попробуй уточнить название.")

    try:
        await status_msg.edit_text("⚡️ Загружаю в Telegram...")
        with open(file_path, 'rb') as audio:
            await message.answer_audio(audio, caption=f"🎶 **{title}**\nПриятного прослушивания! ✨")
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки файла: {e}")

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    print("Бот успешно запущен!")
    executor.start_polling(dp, skip_updates=True)