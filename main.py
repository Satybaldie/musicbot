# Создаем меню с обновленными кнопками
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = KeyboardButton("🔍 Найти песню")
    btn_downloaded = KeyboardButton("📥 Скачанные")
    btn_wave = KeyboardButton("🌊 Моя волна")
    btn_playlists = KeyboardButton("📂 Мои Плейлисты")
    
    # Распределяем кнопки по рядам для красоты
    markup.row(btn_search, btn_downloaded)
    markup.row(btn_wave, btn_playlists)
    return markup

# Обработка новых кнопок
@dp.message_handler(lambda message: message.text == "🔍 Найти песню")
async def search_help(message: types.Message):
    await message.answer("🎵 Чтобы найти песню, просто **напиши её название или слова из неё** прямо в этот чат!")

@dp.message_handler(lambda message: message.text == "📥 Скачанные")
async def downloaded_info(message: types.Message):
    await message.answer("📥 Все скачанные песни находятся в твоём чате с ботом. Ты можешь нажать на три точки у файла и выбрать **'Сохранить в музыку'** на телефоне!")

# Остальные обработчики (Wave и Playlists) оставляем как были
@dp.message_handler(lambda message: message.text == "🌊 Моя волна")
async def wave_info(message: types.Message):
    await message.answer("🌊 **Функция «Моя волна» в разработке!**\nСовсем скоро я смогу предлагать тебе треки, которые точно попадут в твой плейлист. 😉")

@dp.message_handler(lambda message: message.text == "📂 Мои Плейлисты")
async def playlist_info(message: types.Message):
    await message.answer("📂 **Твои плейлисты:**\nЧтобы добавить плейлист, просто пришли на него ссылку из YouTube или SoundCloud!")