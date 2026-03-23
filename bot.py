import discord
import datetime
from discord.ext import commands, tasks
from zoneinfo import ZoneInfo
from config.config import DISCORD_TOKEN, COMMAND_PREFIX
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

    if not check_for_updates.is_running():
        check_for_updates.start()


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

@tasks.loop(minutes=15)
async def check_for_updates():
    """ Poll for new Valorant articles on a resource-aware schedule.

    Checks every 15 minutes on Tuesdays during the patch notes window (8 AM - 12 PM EST),
    and once per day at 8 AM EST on all other days.
    """
    now = datetime.datetime.now(ZoneInfo("America/New_York"))
    is_patch_window = now.weekday() == 1 and 8 <= now.hour < 12
    is_daily_check_time = now.hour == 8 and now.minute < 15

    if not is_patch_window and not is_daily_check_time:
        return

    print(f"[CHECK] Running update check at {now} (patch_window={is_patch_window})")

    try:
        await do_valorant_check()
    except Exception as e:
        print(f"[ERROR] Update check failed: {e}")


async def do_valorant_check():
    """ Check for a new article and post it if found. """

    try:
        current_url = get_latest_article_url()
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest article URL: {e}")
        return

    last_url = get_last_article('valorant')

    if current_url == last_url:
        return  # No new article

    if last_url is None:
        # First run: initialize tracking without posting
        set_last_article('valorant', current_url)
        print(f"[INFO] Initialized tracking with {current_url}")
        return

    # New article detected — fetch content before saving URL so we can retry on failure
    print(f"[INFO] New article detected: {current_url}")
    try:
        text_content, article_url, content_type = get_latest_patch_notes()
    except Exception as e:
        print(f"[ERROR] Failed to fetch article content: {e}")
        return  # Don't save URL — will retry on next cycle

    for guild in client.guilds:
        channel_id = get_channel(guild.id, 'valorant')
        if channel_id is None:
            continue

        channel = client.get_channel(channel_id)
        if not channel:
            continue

        try:
            if content_type == 'video':
                await channel.send(f"🔗 New Valorant video posted! : {article_url}")
            else:
                chunks = smart_chunk(text_content)
                for chunk in chunks:
                    await channel.send(chunk)
                await channel.send(f"\n\n🔗 Full article: {article_url}")
        except Exception as e:
            print(f"[ERROR] Failed to post to {guild.name}: {e}")

    # Save URL only after posting has been attempted for all guilds
    set_last_article('valorant', current_url)


@check_for_updates.before_loop
async def before_check():
    await client.wait_until_ready()


# --- Run ---

if __name__ == '__main__':
    client.run(DISCORD_TOKEN)
