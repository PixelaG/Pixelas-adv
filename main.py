import discord
import pymongo
import os
from threading import Thread
from discord.ext import commands
from flask import Flask
from pymongo import MongoClient

# Flask setup
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()

keep_alive()

# MongoDB Atlas-ის კავშირის სტრინგი
mongo_uri = os.getenv("MONGODB_URI")  # MongoDB Atlas-ის კავშირის სტრინგი
client = MongoClient(mongo_uri)
db = client['discord_advertiser']
advertisements = db['advertisements']
channels = db['channels']
log_channels = db['log_channels']

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# /createadv ქომანდი, რომელიც ქმნის რეკლამას
@bot.command()
async def createadv(ctx, *, message: str):
    advertisements.insert_one({"message": message})
    await ctx.send("რეკლამა წარმატებით შეიქმნა!")

# /addchannel ქომანდი, რომელიც არხს უმატებს MongoDB-ში
@bot.command()
async def addchannel(ctx, channel_id: int):
    channels.insert_one({"channel_id": channel_id})
    await ctx.send(f"ჩანაწერი {channel_id} წარმატებით დაემატა!")

# /sendadv ქომანდი, რომელიც გაგზავნის რეკლამას ყველა არხზე
@bot.command()
async def sendadv(ctx):
    adv = advertisements.find_one()  # აიღებს ბოლო რეკლამას
    if adv:
        message = adv["message"]
        all_channels = channels.find()
        for channel in all_channels:
            try:
                channel_id = channel["channel_id"]
                channel_obj = bot.get_channel(channel_id)
                if channel_obj:
                    await channel_obj.send(message)
                    # ლოგის გაგზავნა
                    log_channel = log_channels.find_one()
                    if log_channel:
                        log_channel_obj = bot.get_channel(log_channel["channel_id"])
                        if log_channel_obj:
                            await log_channel_obj.send(f"რეკლამა გაგზავნილია არხზე {channel_id}")
            except Exception as e:
                print(f"მომხმარებლის არხზე {channel_id} გაგზავნა ვერ მოხერხდა: {e}")
        await ctx.send("რეკლამა გაგზავნილია ყველა არხზე!")
    else:
        await ctx.send("რეკლამა არ არის შექმნილი!")

# /addlogchannel ქომანდი, რომელიც ლოგის არხს დააყენებს
@bot.command()
async def addlogchannel(ctx, channel_id: int):
    log_channels.delete_many({})  # წაშლის წინა ლოგ არხს
    log_channels.insert_one({"channel_id": channel_id})
    await ctx.send(f"ლოგ არხი წარმატებით დაინსტალირდა: {channel_id}")

# ბოტის სტარტი
@bot.event
async def on_ready():
    print(f"ბოტი შეყვანილია როგორც {bot.user}")

# ბოტის გაშვება
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
