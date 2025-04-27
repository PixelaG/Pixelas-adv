import discord
import pymongo
import os
from threading import Thread
from discord import app_commands
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

# MongoDB Atlas-ის კავშირი
mongo_uri = os.getenv("MONGODB_URI")  # MongoDB Atlas-ის URI
client = pymongo.MongoClient(mongo_uri)
db = client['discord_advertiser']
advertisements = db['advertisements']

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# /createadv ქომანდი - შექმნის რეკლამას და შეინახავს MongoDB-ში
@app_commands.describe(message="შეტყობინება, რომელიც გსურს რომ შეიქმნას რეკლამა")
@bot.tree.command(name="createadv", description="შექმენით რეკლამა, რომელიც გაგზავნდება არხებზე")
async def createadv(interaction: discord.Interaction, message: str):
    try:
        # თავდაპირველად ინტერკაციონი უნდა დავამუშავოთ defer-ით
        await interaction.response.defer(ephemeral=True)

        # MongoDB-ში შეტყობინების შენახვა
        advertisements.insert_one({"message": message})

        # წარმატებული შეტყობინება
        embed = discord.Embed(title="🟢 რეკლამა წარმატებით შეიქმნა", description=message, color=discord.Color.green())
        embed.set_footer(text=f"შექმნილია {interaction.user.display_name}")

        # ახლა შეგვიძლია გაგზავნოთ საბოლოო პასუხი
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"შეცდომა createadv-ში: {e}")
        await interaction.followup.send("შეცდომა მოხდა! სცადეთ თავიდან.", ephemeral=True)

# /addchannel ქომანდი - არხის დამატება MongoDB-ში
@app_commands.describe(channel_id="Discord არხის ID, სადაც უნდა გაიგზავნოს რეკლამა")
@bot.tree.command(name="addchannel", description="დამატეთ არხი სადაც გსურთ გაგზავნა")
async def addchannel(interaction: discord.Interaction, channel_id: str):
    try:
        # არხის ID-ც უნდა გადატანილი იყოს integer ტიპზე
        channel_id = int(channel_id)
        
        # MongoDB-ში არხის ID-ის დამატება
        db.channels.insert_one({"channel_id": channel_id})
        await interaction.response.send_message(f"არხი {channel_id} წარმატებით დაემატა!", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("გთხოვთ, შეიყვანოთ სწორი არხის ID (მხოლოდ რიცხვი).", ephemeral=True)
    except Exception as e:
        print(f"შეცდომა addchannel-ში: {e}")
        await interaction.response.send_message("შეცდომა მოხდა! სცადეთ თავიდან.", ephemeral=True)

# /sendadv ქომანდი - გაგზავნის რეკლამას ყველა არხზე
@bot.tree.command(name="sendadv", description="გაგზავნეთ შექმნილი რეკლამა ყველა არხზე")
async def sendadv(interaction: discord.Interaction):
    # MongoDB-ში დაცული რეკლამა
    adv = advertisements.find_one()
    if adv:
        message = adv["message"]
        all_channels = db.channels.find()

        for channel in all_channels:
            try:
                channel_obj = bot.get_channel(channel["channel_id"])
                if channel_obj:
                    await channel_obj.send(message)
                    # ლოგის შეტყობინება
                    log_channel = db.log_channels.find_one()
                    if log_channel:
                        log_channel_obj = bot.get_channel(log_channel["channel_id"])
                        if log_channel_obj:
                            await log_channel_obj.send(f"რეკლამა გაგზავნილია არხზე {channel['channel_id']}")
            except Exception as e:
                print(f"მომხმარებლის არხზე {channel['channel_id']} გაგზავნა ვერ მოხერხდა: {e}")

        await interaction.response.send_message("რეკლამა წარმატებით გაგზავნილია ყველა არხზე!", ephemeral=True)
    else:
        await interaction.response.send_message("რეკლამა არ არის შექმნილი!", ephemeral=True)

# /addlogchannel ქომანდი - ლოგის არხის დამატება
@app_commands.describe(channel_id="Discord არხის ID, სადაც გსურთ ლოგების მიღება")
@bot.tree.command(name="addlogchannel", description="დამატეთ ლოგების არხი")
async def addlogchannel(interaction: discord.Interaction, channel_id: int):
    # MongoDB-ში ლოგის არხის ID-ის შენახვა
    db.log_channels.delete_many({})  # წაშლის წინა ლოგ არხს
    db.log_channels.insert_one({"channel_id": channel_id})
    await interaction.response.send_message(f"ლოგ არხი {channel_id} წარმატებით დაინსტალირდა!", ephemeral=True)

# ბოტის გაშვება
@bot.event
async def on_ready():
    print(f"ბოტი შეყვანილია როგორც {bot.user}")
    try:
        # ხელით რეგისტრირება
        await bot.tree.sync()
        print("Slash ქომანდები დარეგისტრირდა.")
    except Exception as e:
        print(f"შეცდომა ქომანდების რეგისტრაციაში: {e}")

# ბოტის გაშვება
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
