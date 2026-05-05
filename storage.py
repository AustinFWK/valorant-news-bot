import os
import json

STORAGE_FILE = "channel_config.json"
LAST_ARTICLE = "last_article.json"

def load_config():
    """Load the channel configuration from a JSON file."""
    if not os.path.exists(STORAGE_FILE):
        return {}
    
    with open(STORAGE_FILE, 'r') as f:
        return json.load(f)
    
def save_config(config):
    """Save the channel configuration to a JSON file."""
    with open(STORAGE_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def set_channel(guild_id, game, channel_id):
    """Set the channel ID for a specific game in a guild."""
    config = load_config()

    #set guild id if not present
    guild_key = str(guild_id)
    if guild_key not in config:
        config[guild_key] = {}
    
    config[guild_key][game] = channel_id
    save_config(config)

def clear_channel(guild_id, game):
    """Clear the channel ID for a specific game in a guild."""
    config = load_config()
    guild_key = str(guild_id)

    if guild_key in config and game in config[guild_key]:
        del config[guild_key][game]
        if not config[guild_key]:  # If no games left for the guild, remove the guild entry
            del config[guild_key]
        save_config(config)

def get_channel(guild_id, game):
    """Get the channel ID for a specific game in a guild."""
    config = load_config()
    guild_key = str(guild_id)

    if guild_key not in config:
        return None

    return config[guild_key].get(game)

def get_last_article(game):
    """Get the last stored article URL for a specific game."""
    if not os.path.exists(LAST_ARTICLE):
        return None

    with open(LAST_ARTICLE, 'r') as f:
        data = json.load(f)
    
    return data.get(game)

def set_last_article(game, article_url):
    """Set the last stored article URL for a specific game."""
    
    if os.path.exists(LAST_ARTICLE):
        with open(LAST_ARTICLE, 'r') as f:
            data = json.load(f)
    else:
        data = {}
    
    data[game] = article_url

    with open(LAST_ARTICLE, 'w') as f:
        json.dump(data, f, indent=2)
