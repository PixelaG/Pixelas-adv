import discord
import pymongo
import os
from discord import TextChannel
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
intents.guilds = True  # საჭიროა სერვერების ნახვისთვის
bot = commands.Bot(command_prefix='/', intents=intents)

# /createadv ქომანდი - შექმნის რეკლამას და შეინახავს MongoDB-ში
@app_commands.describe(message="შეტყობინება, რომელიც გსურთ რომ შეიქმნას რეკლამა")
@bot.tree.command(name="createadv", description="შექმენით რეკლამა, რომელიც გაგზავნდება არხებზე")
async def createadv(interaction: discord.Interaction, message: str):
    try:
        # შემოწმება თუ არ არსებობს იგივე რეკლამა
        existing_adv = advertisements.find_one({"message": message})

        if existing_adv:
            await interaction.response.send_message("ეს რეკლამა უკვე არსებობს!", ephemeral=True)
            return

        # MongoDB-ში შეტყობინების შენახვა
        advertisements.insert_one({
            "message": message,
            "user_id": interaction.user.id  # ვინმემ გამოიყენა ქომანდი
        })

        # წარმატებული შეტყობინება
        embed = discord.Embed(title="🟢 რეკლამა წარმატებით შეიქმნა", description=message, color=discord.Color.green())
        embed.set_footer(text=f"შექმნილია {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"Error occurred while creating advertisement: {e}")
        # მხოლოდ ერთხელ გავაგზავნოთ შეტყობინება
        if not interaction.response.is_done():
            await interaction.response.send_message("შეცდომა მოხდა! სცადეთ თავიდან.", ephemeral=True)

# /addchannel ქომანდი - არხის დამატება MongoDB-ში
@app_commands.describe(server_id="Discord სერვერის ID, სადაც უნდა დაემატოს არხი", channel_id="Discord არხის ID, სადაც უნდა გაიგზავნოს რეკლამა")
@bot.tree.command(name="addchannel", description="დამატეთ არხი და სერვერი MongoDB-ში")
async def addchannel(interaction: discord.Interaction, server_id: str, channel_id: str):
    try:
        # შეამოწმეთ რომ server_id და channel_id არის მთლიანი რიცხვები
        if not server_id.isdigit() or not channel_id.isdigit():
            await interaction.response.send_message("თქვენი მითითებული ID-ები არ არის სწორი ტიპის. გთხოვთ, მიუთითოთ მთლიანი რიცხვები.", ephemeral=True)
            return
        
        # კონვერტაცია int ფორმატში
        server_id = int(server_id)
        channel_id = int(channel_id)

        # MongoDB-ში სერვერის ID და არხის ID-ის შენახვა
        db.channels.insert_one({"server_id": server_id, "channel_id": channel_id})

        await interaction.response.send_message(f"არხი {channel_id} წარმატებით დაემატა სერვერზე {server_id}!", ephemeral=True)
    except Exception as e:
        print(f"შეცდომა მოხდა არხის დამატების დროს: {e}")
        await interaction.response.send_message("შეცდომა მოხდა! სცადეთ თავიდან.", ephemeral=True)

# /sendadv ქომანდი - გაგზავნის რეკლამას ყველა არხზე
@bot.tree.command(name="sendadv", description="გაგზავნეთ შექმნილი რეკლამა ყველა არხზე")
async def sendadv(interaction: discord.Interaction, server_id: int):
    try:
        # MongoDB-ში დაცული რეკლამა
        adv = advertisements.find_one()
        if adv:
            message = adv["message"]
            # MongoDB-ში არხების ძებნა სერვერის ID-ის მიხედვით
            all_channels = db.channels.find({"server_id": server_id})

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
                                await log_channel_obj.send(f"რეკლამა გაგზავნილია არხზე {channel['channel_id']} სერვერზე {server_id}")
                except Exception as e:
                    print(f"მომხმარებლის არხზე {channel['channel_id']} გაგზავნა ვერ მოხერხდა: {e}")

            await interaction.response.send_message(f"რეკლამა წარმატებით გაგზავნილია ყველა არხზე სერვერზე {server_id}!", ephemeral=True)
        else:
            await interaction.response.send_message("რეკლამა არ არის შექმნილი!", ephemeral=True)
    except Exception as e:
        print(f"შეცდომა: {e}")
        await interaction.response.send_message("შეცდომა მოხდა! სცადეთ თავიდან.", ephemeral=True)

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
