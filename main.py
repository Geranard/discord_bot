import discord
import os
import time
import threading
import asyncio
from discord.errors import ClientException
from discord.ext import commands
from discord.ext.commands.core import check
from youtube_dl import YoutubeDL
from youtube_dl.utils import DownloadError
import requests
from bs4 import BeautifulSoup
import urllib
import re
import random

# ---------------------------- global var ---------------------------- #
token = os.environ.get("DISCORD_TOKEN")
music_queue = []
queue_player = []
original_queue = []
flag_queue = [0]*9999
now = 0
play_title = ""
flag_is_playing = False
flag_is_downloading = False
flag_is_shuffled = False

# ---------------------------- init ---------------------------- #
bot = commands.Bot(command_prefix="-")

# ---------------------------- status ---------------------------- #
@bot.event
async def on_ready():
    print(f"User {bot.user} has connected to discord.")

# ---------------------------- server info ---------------------------- #
@bot.command(name="server-info", aliases=["info"])
async def server(context):
    if context.author==bot.user:
        return
    
    name = str(context.guild.name)
    description = str(context.guild.description)
    owner = str(context.guild.owner)
    id = str(context.guild.id)
    region = str(context.guild.region)
    member_count = str(context.guild.member_count)
    icon = str(context.guild.icon_url)

    embed = discord.Embed(
        title=name + " Server Information",
        description=description,
        color=discord.Color.blue()
    )
    
    embed.set_thumbnail(url=icon)
    embed.add_field(name="Owner", value=owner, inline=True)
    embed.add_field(name="Server ID", value=id, inline=True)
    embed.add_field(name="Region", value=region, inline=True)
    embed.add_field(name="Member Count", value=member_count, inline=True)
    
    await context.send(embed=embed)

# ---------------------------- help command ---------------------------- #
bot.remove_command("help")
@bot.command(name="help", aliases=["h"])
async def help(context):
    message = "```"
    message += "               Met dateng ke hjelp page.\n\n"
    message += "-play [url]/-p      -> untuk masukin queue lagu sama mainin\n"
    message += "-leave              -> botnya keluar sama ngebersihin queuenya\n"
    message += "-pause              -> botnya pause aja\n"
    message += "-resume             -> ngelanjutin lagu yang di pause lah\n"
    message += "-clear               -> botnya tetep di dalem, cuma queue diapus sama lagunya berenti\n"
    message += "-queue              -> nunjukin lagu apa aja yang di queue sama yang dimainin\n"
    message += "Kerapihan kagak sih ini helpnya?\n"
    message += "```"
    await context.send(message)

# ---------------------------- now playing command ---------------------------- #
@bot.command(name="now-playing", aliases=["np"])
async def now_playing(context):
    global now, music_queue
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")

    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Ga, ga ada, pegi sana liat liat aja.")
        
    if len(music_queue)<=0:
        return await context.send("Yo ndak tau, kok tanya saya?")
    
    await context.send(f"Lagi muterin {music_queue[now-1]['title']}")

# ---------------------------- queue command ---------------------------- #
@bot.command(name="queue", aliases=["q"])
async def queue(context):
    global now, music_queue
    if context.author.voice.channel!=context.voice_client.channel:
        await context.send("Siapa anda, kagak join maen liat queue orang aja.")
        return

    if len(music_queue)<=0:
        message = "Ga ada musiknya ini."
    
    else:
        message = "```"
        from_ = 0
        to_ = len(music_queue)

        if now>=10:
            from_ = now-10
        
        if now+10<=len(music_queue):
            to_ = now+10
        
        for idx in range(from_, to_):
            if idx == now-1:
                message += " -> Now Playing\n"
                message += f"{idx+1}) {music_queue[idx]['title']}\n"
                message += " -> Now Playing\n"

            else:
                message += f"{idx+1}) {music_queue[idx]['title']}\n"

        message += "```"
    
    await context.send(message)

# ---------------------------- task play ---------------------------- #
def tasks_play(voice_client):
    async def is_busy():
        global now
        if now<=len(music_queue) and not voice_client.is_playing():
            await play_music(voice_client)

    def buffer():
        while flag_is_playing == True:
            asyncio.run(is_busy())
    
    global flag_is_playing
    task = threading.Thread(target=buffer)
    task.daemon = True

    if flag_is_playing is False:
        flag_is_playing = True
        task.start()

# ---------------------------- play music ---------------------------- #
async def play_music(voice_client):
    global now, music_queue
    voice_client.stop()
    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }
    if now<len(music_queue):
        now_playing = music_queue[now]["url"]
        source = await discord.FFmpegOpusAudio.from_probe(now_playing, **ffmpeg_options)
        voice_client.play(source)
        flag_queue[now] = 1
        now += 1

# ---------------------------- task download ---------------------------- #
def tasks_download(url, context, voice_channel):
    async def is_busy():
        await extract_music(url, context, voice_channel)

    def buffer():
        asyncio.run(is_busy())

    global flag_is_downloading
    task = threading.Thread(target=buffer)
    task.daemon = True

    if flag_is_downloading == False:
        flag_is_downloading = True
        task.start()

# ---------------------------- scrap playlist ---------------------------- #
def title_scraper(url):
    response = requests.get(url).text
    soup = BeautifulSoup(response, "html.parser")
    title = soup.title.text

    if "youtube.com" in url:
        title = title.replace(" - YouTube", "")

    elif "soundcloud.com" in url:
        title = title.replace("Stream ", "").replace(" | Listen online for free on SoundCloud", "")

    return title

# ---------------------------- extract music ---------------------------- #
async def extract_music(url, context, voice_channel):
    global play_title, music_queue, flag_is_downloading
    try:
        play_title = title_scraper(url)

        ytdl_opts = {
            "cookiefile": "cookies.txt",
            "format": "best",
            "default_search": "auto",
        }

        ytdl = YoutubeDL(ytdl_opts)
        info = ytdl.extract_info(url, download=False)

        if "?list=" in url:
            length = len(info["entries"])
            for index in range(length):
                link = info["entries"][index]["url"]
                title = info["entries"][index]["title"]
                duration = info["entries"][index]["duration"]
                music_dict = {
                    "url": link,
                    "title": title,
                    "duration": duration,
                    "guild": str(context.guild),
                    "channel": voice_channel,
                }
                music_queue.append(music_dict)

        else:
            link = info["url"]
            title = info["title"]
            duration = info["duration"]
            music_dict = {
                "url": link,
                "title": title,
                "duration": duration,
                "guild": str(context.guild),
                "channel": voice_channel,
            }
            music_queue.append(music_dict)
        
        print(f"EXTRACT MUSIC FUNCTION TRIGGERED SAFELY")
    
    except DownloadError:
        return

    flag_is_downloading = False

# ---------------------------- play command ---------------------------- #
@bot.command(name="play", aliases=["p"])
async def play(context, *, search):
    global music_queue, play_title
    try:
        voice_channel = str(context.author.voice.channel)
        voice = discord.utils.get(context.guild.voice_channels, name=voice_channel)
        print(f"Bot connected to {voice_channel} at {context.guild}")
        await voice.connect()

    except AttributeError:
        return await context.send("Anda tidak join ke kanal manapun di channel ini. Jbjb boleh lah.")

    except ClientException:
        print(f"Bot already in {voice_channel} at {context.guild}")
    
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)

    if not ".com" in search and not ".org" in search:
        query_string = urllib.parse.urlencode({
            'search_query': search
        })

        html_content = urllib.request.urlopen(
            'https://www.youtube.com/results?search_query=' + query_string
        )

        search_results = re.findall(r'watch\?v=\w+', html_content.read().decode())
        search_results = [result for result in search_results if len(result)==19]
        search = f"https://www.youtube.com/{search_results[0]}"

    tasks_play(voice_client)
    tasks_download(search, context, voice_channel)
    time.sleep(3)
    tasks_play(voice_client)

    if "?list=" in search:
        await context.send(f"Ngantriin playlist {play_title}.")
    else:
        await context.send(f"Ngantriin musik {play_title}.")

    print(f"PLAY COMMAND FUNCTION TRIGGERED SAFELY")

# ---------------------------- next command ---------------------------- #
@bot.command(name="next", aliases=["n", "skip"])
async def next(context):
    global now, music_queue, flag_is_playing
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel
    
    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")

    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau sekap sekip aja.")
    
    flag_is_playing = False

    if now>=len(music_queue):
        voice_client.stop()
        time.sleep(1)
        return await context.send("Dah abis.")

    if len(music_queue)<0:
        return await context.send("Mau skip apa kau? Queuenya aja kosong, kayak dompet saya.")

    await context.send(f"Move on dari {music_queue[now-1]['title']} ke {music_queue[now]['title']}.")
    voice_client.stop()
    time.sleep(1)

    tasks_play(voice_client)

# ---------------------------- previous command ---------------------------- #
@bot.command(name="prev", aliases=["back"])
async def prev(context):
    global now, music_queue, flag_is_playing
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")

    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau prev prev aja.")
    
    flag_is_playing = False

    if now<=0:
        return await context.send("Mau prev apa kau? Sebelomnya aja kagak ada.")

    if len(music_queue)<=0:
        return await context.send("Mau prev apa kau? Queuenya aja kosong, kayak dompet saya.")

    await context.send(f"Gagal move on dari {music_queue[now-1]['title']} ke {music_queue[now-2]['title']}.")
    now -= 2
    voice_client.stop()
    time.sleep(1)
    
    tasks_play(voice_client)

# ---------------------------- jump command ---------------------------- #
@bot.command(name="jump", aliases=["j"])
async def jump(context, index):
    global now, music_queue, flag_is_playing
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Sayanya masukin dulu lah.")

    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau jump jump aja.")
    
    now = int(index)-1
    await context.send(f"Ngelompat ke {music_queue[now]['title']}")
    voice_client.stop()
    time.sleep(2)

    flag_is_playing = False
    tasks_play(voice_client)

# ---------------------------- shuffle command ---------------------------- #
@bot.command(name="shuffle", aliases=["random", "randomize"])
async def shuffle(context):
    global now, original_queue, flag_queue, flag_is_shuffled
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau jump jump aja.")

    if flag_is_shuffled is False:
        length = len(music_queue)
        original_queue = []
        original_queue.clear()
        for index in range(length):
            original_queue.append(music_queue[index])
        
        for index in range(now):
            music_queue[index] = original_queue[index]

        for index in range(now, length):
            rand_idx = random.randint(now, length-1)
            while flag_queue[rand_idx]==1:
                rand_idx = random.randint(now, length-1)

            music_queue[index] = original_queue[rand_idx]
            flag_queue[rand_idx] = 1

        flag_is_shuffled = True
        await context.send("Queue tergocek.")

    elif flag_is_shuffled is True:
        length = len(music_queue)
        for index in range(length):
            music_queue[index] = original_queue[index]

        original_queue.clear()
        flag_is_shuffled = False
        await context.send("Sudah kembali ke semula.")

# ---------------------------- loop command ---------------------------- #
@bot.command(name="loop")
async def loop(context):
    global counter, now
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    if context.author.voice.channel!=context.voice_client.channel:
        await context.send("Anda saja tidak join disini, mau muter aja.")
        return

    # lanjut lagi entar

# ---------------------------- pause command ---------------------------- #
@bot.command(name="pause", aliases=[""])
async def pause(context):
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")
    
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau main pause aja.")

    if voice_client.is_playing():
        voice_client.pause()
    else:
        await context.send("Pause apa gan?")

# ---------------------------- resume command ---------------------------- #
@bot.command(name="resume", alisases=[""])
async def resume(context):
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")
    
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau main resume aja.")
    
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await context.send("Hah? Resume apa nih?")

# ---------------------------- stop command ---------------------------- #
@bot.command(name="stop", alisases=[""])
async def stop(context):
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")
    
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau main stop aja.")
    
    await context.send("Fungsi stop masih di develop. Sabar ya.")

# ---------------------------- remove command ---------------------------- #
@bot.command(name="remove", aliases=["r"])
async def remove(context, index):
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")
    
    if context.author.voice.channel!=context.voice_client.channel:
        await context.send("Anda saja tidak join disini, mau main remove playlist orang aja.")
        return
    
    index = int(index)
    index -= 1
    try:
        music_queue.pop(index)

        if now-1 == index:
            voice_client.stop()
            play_music(voice_client)
        
        await context.send(f"Ngeremove {music_queue[index-1]['title']}.")

    except IndexError:
        await context.send(f"Ada yang ngaco ini. Antara ga ada indexnya atau mabok.")

# ---------------------------- clear command ---------------------------- #
@bot.command(name="clear", aliases=["c", "purge"])
async def clear(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")
    
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau main clear playlist orang aja.")

    voice_client.stop()
    flag_is_playing = False
    flag_is_downloading = False
    flag_is_shuffled = False
    now = 0
    music_queue.clear()
    flag_queue = [0]*9999
    time.sleep(1)
    await context.send("Dah di clear.")

# ---------------------------- leave command ---------------------------- #
@bot.command(name="leave", aliases=["dc"])
async def leave(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau main depak bot orang aja.")
    
    voice_client.stop()
    await context.send("Sip pergi dulu.")
    flag_is_playing = False
    flag_is_downloading = False
    flag_is_shuffled = False
    now = 0
    music_queue.clear()
    time.sleep(1)
    await voice_client.disconnect()

# ---------------------------- deploy the bot ---------------------------- #
bot.run(token)
