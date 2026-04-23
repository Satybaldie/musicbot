import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

# Настройка интентов (прав доступа)
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# Настройки для музыки
YDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': 'True', 'quiet': True}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user.name} успешно запущен и готов играть музыку!')

@bot.command()
async def play(ctx, *, search):
    """Команда для поиска и игры: !play [название]"""
    if not ctx.author.voice:
        return await ctx.send("Сначала зайди в голосовой канал!")

    vc = ctx.guild.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect()

    async with ctx.typing():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{search}", download=False)['entries'][0]
                url = info['url']
                title = info['title']
            except Exception as e:
                return await ctx.send(f"Ошибка поиска: {e}")

        # Если что-то уже играет, останавливаем
        if vc.is_playing():
            vc.stop()

        source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
        vc.play(source)
        await ctx.send(f'🎶 Сейчас играет: {title}')

@bot.command()
async def stop(ctx):
    """Остановка и выход: !stop"""
    if ctx.guild.voice_client:
        await ctx.guild.voice_client.disconnect()
        await ctx.send("Музыка выключена, до связи!")

# Берем токен из переменных Railway
token = os.getenv('BOT_TOKEN')
if token:
    bot.run(token)
else:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена в настройках Railway!")