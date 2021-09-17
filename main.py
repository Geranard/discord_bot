import discord
import os
import time
import threading
import asyncio
from discord.errors import ClientException
from discord.ext import commands
from youtube_dl import YoutubeDL
from youtube_dl.utils import DownloadError
import requests
import urllib
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import re

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
flag_is_looping = False

# ---------------------------- init ---------------------------- #
bot = commands.Bot(command_prefix="-")

# ---------------------------- status ---------------------------- #
@bot.event
async def on_ready():
    print(f"User {bot.user} has connected to discord.")

# ---------------------------- server info ---------------------------- #
@bot.command(
    name="server-info",
    aliases=["info"],
    help="Ngasih informasi tentang server ini"
)
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

# ---------------------------- now playing command ---------------------------- #
@bot.command(
    name="now-playing",
    aliases=["np"],
    help="Bisa ngasih tau apa yang lagi di play sekarang"
)
async def now_playing(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping

    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")

    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Ga, ga ada, pegi sana liat liat aja.")
        
    if len(music_queue)<=0:
        return await context.send("Yo ndak tau, kok tanya saya?")
    
    await context.send(f"Lagi muterin {music_queue[now-1]['title']}")

# ---------------------------- queue command ---------------------------- #
@bot.command(
    name="queue",
    aliases=["q"],
    help="Ngasih tau queue lagunya"
)
async def queue(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping

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
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping

    async def is_busy():
        global now
        if now<len(music_queue) and not voice_client.is_playing():
            await play_music(voice_client)

    def buffer():
        while flag_is_playing == True:
            asyncio.run(is_busy())

    task = threading.Thread(target=buffer)
    task.daemon = True

    if flag_is_playing is False:
        flag_is_playing = True
        task.start()

# ---------------------------- play music ---------------------------- #
async def play_music(voice_client):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping

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
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
    
    async def is_busy():
        await extract_music(url, context, voice_channel)

    def buffer():
        asyncio.run(is_busy())

    task = threading.Thread(target=buffer)
    task.daemon = True

    if flag_is_downloading == False:
        flag_is_downloading = True
        task.start()

# ---------------------------- scrap title ---------------------------- #
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
    global now, play_title, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
    try:
        play_title = title_scraper(url)

        ytdl_opts = {
            "cookiefile": "cookies.txt",
            "format": "best",
            "default_search": "auto",
        }

        ytdl = YoutubeDL(ytdl_opts)

        if "?list=" in url:
            path = "C:\Development\chromedriver.exe"
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36"

            opts = webdriver.ChromeOptions()
            opts.add_argument(f"user-agent={user_agent}")
            opts.add_argument("--headless")
            opts.add_argument("log-level=3")

            driver = webdriver.Chrome(executable_path=path, options=opts)
            driver.get(url)

            soup = BeautifulSoup(driver.page_source, "lxml")

            videos = int(soup.find("span", {"class": "style-scope yt-formatted-string"}).text)
            scroll = int(videos / 100)
            if scroll>0:
                element = driver.find_element_by_tag_name("html")
                element.send_keys(Keys.END)
                for _ in range(scroll):
                    time.sleep(1)
                    element.send_keys(Keys.END)
                
                soup = BeautifulSoup(driver.page_source, "lxml")

            with open(file="tes.html", mode="w", encoding="utf-8") as file:
                file.write(str(soup.prettify))

            titles = soup.find_all(
                "a",
                {
                    "id": "video-title",
                    "class": "yt-simple-endpoint style-scope ytd-playlist-video-renderer"
                }
            )

            for title in titles:
                link = re.findall(r'href=\"\/watch\?v=(.{11})', str(title))
                link = f"https://www.youtube.com/watch?v={link[0]}"

                title = f"{title.text}"
                title = title.replace("\n", "").replace(" ", "", 10)

                info = ytdl.extract_info(link, download=False)

                if flag_is_downloading == False:
                    return

                music_dict = {
                    "url": info["url"],
                    "title": info["title"],
                    "guild": str(context.guild),
                    "channel": voice_channel,
                }
                music_queue.append(music_dict)

            driver.close()

        else:
            info = ytdl.extract_info(url, download=False)

            if flag_is_downloading == False:
                return
            
            music_dict = {
                "url": info["url"],
                "title": info["title"],
                "guild": str(context.guild),
                "channel": voice_channel,
            }
            music_queue.append(music_dict)

        print(f"EXTRACT MUSIC FUNCTION TRIGGERED SAFELY")

    except DownloadError:
        return

    flag_is_downloading = False

# ---------------------------- play command ---------------------------- #
@bot.command(
    name="play",
    aliases=["p"],
    help="Kalo mau play lagu dan masukin ke queue"
)
async def play(context, *, search):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
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

    if not ".com" in search and not ".org" in search and not "https://" in search:
        query_string = urllib.parse.urlencode({
            'search_query': search
        })

        html_content = urllib.request.urlopen(
            'https://www.youtube.com/results?search_query=' + query_string
        )

        search_results = re.findall(r'watch\?v=\w+', html_content.read().decode())
        search_results = [result for result in search_results if len(result)==19]
        search = f"https://www.youtube.com/{search_results[0]}"

    tasks_download(search, context, voice_channel)
    time.sleep(5)
    tasks_play(voice_client)

    if "?list=" in search:
        await context.send(f"Ngantriin playlist {play_title}.")
    else:
        await context.send(f"Ngantriin musik {play_title}.")

    print(f"PLAY COMMAND FUNCTION TRIGGERED SAFELY")

# ---------------------------- next command ---------------------------- #
@bot.command(
    name="next",
    aliases=["n", "skip"],
    help="Kalo ga suka lagunya, bisa skip atau next aja"
)
async def next(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
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
@bot.command(
    name="prev",
    aliases=["back"],
    help="Kalo mau balik ke lagu sebelumnya"
)
async def prev(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
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
@bot.command(
    name="jump",
    aliases=["j"],
    help="Mau loncat ke urutan lagu tertentu, masukin aja angkanya"
)
async def jump(context, index):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
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
@bot.command(
    name="shuffle",
    aliases=["random", "randomize"],
    help="Ngacak-ngacak queue, tapi masih ccd ini commandnya"
)
async def shuffle(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau jump jump aja.")

    if flag_is_shuffled is False:
        length = len(music_queue)
        original_queue.clear()

        for index in range(length):
            original_queue.append(music_queue[index])

        music_queue.clear()
        for index in range(now):
            print(f"init index -> {index}")
            music_queue.append(original_queue[index])

        for index in range(now, length):
            print(f"shuffle index -> {index}")
            rand_idx = random.randint(now, length-1)
            while flag_queue[rand_idx]==1:
                rand_idx = random.randint(now, length-1)

            music_queue.append(original_queue[rand_idx])
            flag_queue[rand_idx] = 1

        flag_is_shuffled = True
        await context.send("Queue tergocek.")

    elif flag_is_shuffled is True:
        music_queue.clear()
        length = len(original_queue)
        for index in range(length):
            print(original_queue[index]["title"])
            music_queue.append(original_queue[index])

        original_queue.clear()
        flag_is_shuffled = False
        await context.send("Sudah kembali ke semula.")

# ---------------------------- loop command ---------------------------- #
@bot.command(
    name="loop",
    help="Buat ngemuter berkali-kali"
)
async def loop(context):
    global counter, now
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    if context.author.voice.channel!=context.voice_client.channel:
        await context.send("Anda saja tidak join disini, mau muter aja.")
        return

    # lanjut lagi entar

# ---------------------------- pause command ---------------------------- #
@bot.command(
    name="pause",
    help="Kalo lagi jalan lagunya, baru bisa di pause"
)
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
@bot.command(
    name="resume",
    help="Kalo udah di pause, baru bisa di resume"
)
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
@bot.command(
    name="stop",
    help="Stop lagunya aja gitu"
)
async def stop(context):
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    voice_channel = context.author.voice.channel

    if voice_channel is None:
        return await context.send("Saya aja ga masuk cok.")
    
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau main stop aja.")
    
    await context.send("Fungsi stop masih di develop. Sabar ya.")

# ---------------------------- remove command ---------------------------- #
@bot.command(
    name="remove",
    aliases=["r"],
    help="Ngapus lagu dari queuenya, masukin aja indexnya dari queue"
)
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
@bot.command(
    name="clear",
    aliases=["c", "purge"],
    help="Ngapus seluruh queuenya trus berenti mainin lagunya"
)
async def clear(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
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
    flag_is_looping = False
    flag_queue = [0]*9999
    now = 0
    music_queue.clear()
    time.sleep(1)
    await context.send("Dah di clear.")

# ---------------------------- leave command ---------------------------- #
@bot.command(
    name="leave",
    aliases=["dc"],
    help="Ini mah keluarin bot aja"
)
async def leave(context):
    global now, flag_is_playing, flag_is_downloading, flag_is_shuffled, music_queue, flag_queue, flag_is_looping
    voice_client = discord.utils.get(bot.voice_clients, guild=context.guild)
    if context.author.voice.channel!=context.voice_client.channel:
        return await context.send("Anda saja tidak join disini, mau main depak bot orang aja.")
    
    voice_client.stop()
    await context.send("Sip pergi dulu.")
    flag_is_playing = False
    flag_is_downloading = False
    flag_is_shuffled = False
    flag_is_looping = False
    now = 0
    music_queue.clear()
    time.sleep(1)
    await voice_client.disconnect()

# ---------------------------- deploy the bot ---------------------------- #
bot.run(token)
