import os
from dotenv import load_dotenv
import discord
import requests
import json
from discord.ext import commands, tasks

env_path = os.path.join(os.path.dirname(__file__), "config.env")
load_dotenv(dotenv_path=env_path)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
API_NINJAS_KEY = os.getenv("API_NINJAS_KEY")
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN is not being loaded! Check your config.env file.") #for if the discord bot token is improperly formatted

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
LEADERBOARD_FILE = "leaderboard.json" #creates json file for the leaderboard if it does not exist 

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_leaderboard(data):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f)

user_scores = load_leaderboard()
trivia_sessions = {}

@bot.command()
async def trivia(ctx, category: str = None):
    if category:
        url = f"https://api.api-ninjas.com/v1/trivia?category={category}"
        category_used = category
    else:
        url = "https://api.api-ninjas.com/v1/trivia"
        category_used = "unspecified"
    headers = {"X-Api-Key": API_NINJAS_KEY}
    response = requests.get(url, headers=headers)
    print(f"API Response Code: {response.status_code}")
    print(f"API Response Body: {response.text}")
    if response.status_code != 200:
        await ctx.send(f"❌ API Error: {response.status_code} - {response.text}")
        return
    try:
        trivia_data = response.json()
    except Exception as e:
        await ctx.send(f"❌ Error parsing JSON: {e}")
        return
    if not isinstance(trivia_data, list) or len(trivia_data) == 0:
        await ctx.send(f"⚠ No trivia questions found for `{category_used}`. Try another category.")
        return
    first_item = trivia_data[0]
    if not isinstance(first_item, dict):
        await ctx.send("⚠ Unexpected API response format. Try again later.")
        return
    question = first_item.get('question', "No question found.")
    answer = first_item.get('answer', "No answer found.")
    trivia_sessions[ctx.guild.id] = {"question": question, "answer": answer.lower(), "category": category_used}
    await ctx.send(f"🎲 **Category:** {category_used.capitalize()}\n❓ **Question:** {question}\n(Type `!answer your_answer` to respond!)")

@bot.command()
async def answer(ctx, *, user_answer: str):
    if ctx.guild.id not in trivia_sessions:
        await ctx.send("⚠ No active trivia question! Use `!trivia [category]` to start.")
        return
    correct_answer = trivia_sessions[ctx.guild.id]["answer"]
    if user_answer.lower() == correct_answer:
        await ctx.send(f"✅ **Correct!** 🎉 The answer was: **{correct_answer}**")
        user_id_str = str(ctx.author.id)
        user_scores[user_id_str] = user_scores.get(user_id_str, 0) + 1
        save_leaderboard(user_scores)
        del trivia_sessions[ctx.guild.id]
    else:
        await ctx.send("❌ **Incorrect!** Try again.")

@bot.command()
async def leaderboard(ctx):
    if not user_scores:
        await ctx.send("🏆 No scores yet! Start playing with `!trivia [category]`!")
        return
    sorted_scores = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "\n".join([f"<@{user_id}> - **{score}** points" for user_id, score in sorted_scores[:10]])
    await ctx.send(f"📊 **Leaderboard:**\n{leaderboard_text}")

@bot.command()
async def hint(ctx):
    if ctx.guild.id not in trivia_sessions:
        await ctx.send("⚠ No active trivia question!")
        return
    answer = trivia_sessions[ctx.guild.id]["answer"]
    hint_message = f"The answer is {len(answer)} letters long, starts with '{answer[0].upper()}' and ends with '{answer[-1].upper()}'."
    await ctx.send(f"💡 **Hint:** {hint_message}")

@tasks.loop(minutes=120) #loop is a variable 
async def scheduled_trivia():
    channel = bot.get_channel(1064323770715734049)
    if channel:
        url = "https://api.api-ninjas.com/v1/trivia"
        headers = {"X-Api-Key": API_NINJAS_KEY}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            try:
                trivia_data = response.json()
            except Exception as e:
                await channel.send(f"❌ Error parsing trivia JSON: {e}")
                return
            if not isinstance(trivia_data, list) or len(trivia_data) == 0:
                await channel.send("⚠ No trivia questions found for daily trivia. Try again later.")
                return
            first_item = trivia_data[0]
            if not isinstance(first_item, dict):
                await channel.send("⚠ Unexpected API response format for daily trivia.")
                return
            question = first_item.get('question', "No question found.")
            answer = first_item.get('answer', "No answer found.")
            trivia_sessions[channel.guild.id] = {"question": question, "answer": answer.lower(), "category": "daily"}
            await channel.send(f"📅 **Daily Trivia:**\n❓ **Question:** {question}\n(Type `!answer your_answer` to respond!)")
        else:
            await channel.send(f"❌ API Error for daily trivia: {response.status_code} - {response.text}")

@bot.event
async def on_ready():
    scheduled_trivia.start()

bot.run(DISCORD_BOT_TOKEN)
