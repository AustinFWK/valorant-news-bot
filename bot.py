import discord
import datetime
import asyncio
from discord.ext import commands, tasks
from config import DISCORD_TOKEN, COMMAND_PREFIX
from valorant.scraper import get_latest_article_url, get_latest_patch_notes
from valorant.formatter import smart_chunk
from storage import get_last_article, set_channel, get_channel, set_last_article



# Bot setup
intents = discord.Intents.all()
client = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


# --- Events ---

@client.event
async def on_ready():
    print("The bot is ready for use")
    print("------------------------")
    daily_check.start()
    tuesday_patch_notes_check.start()


# --- Commands ---

@client.command()
async def hello(ctx):
    """Simple test command."""
    await ctx.send("hello user")

@client.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx, game: str):
    """Set the current channel to receive updates for a specific game."""
    valid_games = ['valorant']  # Extendable for future games

    game = game.lower()
    if game not in valid_games:
        await ctx.send(f"Invalid game. Valid options are: {', '.join(valid_games)}")
        return
    
    set_channel(ctx.guild.id, game, ctx.channel.id)
    await ctx.send(f"Channel set for {game} updates.")

@client.command()
async def getchannel(ctx, game: str):
    """Get the channel set for a specific game's updates"""
    game = game.lower()
    channel_id = get_channel(ctx.guild.id, game)

    if channel_id:
        await ctx.send(f"The channel for {game} updates is <#{channel_id}>")
    else:
        await ctx.send(f"No channel set for {game} updates. Use !setchannel to set one.")

@setchannel.error
async def setchannel_error(ctx, error):
    """Error handler for setchannel command."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")


@client.command()
async def patchnotes(ctx):
    """Fetch and display the latest Valorant patch notes."""

    try:
        text_content, article_url, content_type = get_latest_patch_notes()

        if content_type == 'video':
            await ctx.send(f"🔗 Latest video: {article_url}")
            return

        chunks = smart_chunk(text_content)

        for chunk in chunks:
            await ctx.send(chunk)

        await ctx.send(f"\n\n🔗 Full article: {article_url}")

    except Exception as e:
        await ctx.send(f"Error fetching patch notes: {str(e)}")

# --- Background Tasks ---

def is_patch_notes_window():
    """ Check if the current time is within the patch notes posting window (Tuesdays 8 AM - 12 PM EST). """
   # Get current time in EST                                                                                                                                                                                                                     
    utc_now = datetime.datetime.now(datetime.timezone.utc)           
    #change hours=-5 to hours=-4 for daylight savings time                                                                                                                                                                             
    est_offset = datetime.timedelta(hours=-4)  # EST is UTC-5                                                                                                                                                                                     
    est_now = utc_now + est_offset 

    is_tuesday = est_now.weekday() == 1  # Tuesday is 1
    is_patch_hours = 8 <= est_now.hour < 12

    return is_tuesday and is_patch_hours

@tasks.loop(hours=24)
async def daily_check():
    if is_patch_notes_window():
        return
    
    await do_valorant_check()

@tasks.loop(minutes=15)
async def tuesday_patch_notes_check():
    """ Frequent checks during patch notes window. """
    if not is_patch_notes_window():
        return
    await do_valorant_check()

async def do_valorant_check():
    """ Shared logic for checking and posting Valorant patch notes. """

    try:
        current_url = get_latest_article_url()
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest patch notes article URL: {e}")
        return
    
    last_url = get_last_article('valorant')

    if current_url == last_url:
        return # No new article
    
   
    set_last_article('valorant', current_url)

    if last_url is None:
        print(f"initialized tracking with {current_url}")
        return # First run, don't post
    
    text_content, article_url, content_type = get_latest_patch_notes()

    for guild in client.guilds:
        channel_id = get_channel(guild.id, 'valorant')
        if channel_id is None:
            continue

        channel = client.get_channel(channel_id)
        if not channel:
            continue

        if content_type == 'video':
            await channel.send(f"🔗 New Valorant video posted! : {article_url}")
        else:
            chunks = smart_chunk(text_content)

            for chunk in chunks:
                await channel.send(chunk)

            await channel.send(f"\n\n🔗 Full article: {article_url}")



@daily_check.before_loop
@tuesday_patch_notes_check.before_loop
async def before_checks():
    await client.wait_until_ready()

        


# --- Run ---

if __name__ == '__main__':
    client.run(DISCORD_TOKEN)
