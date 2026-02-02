import os
import json

STORAGE_FILE = "channel_config.json"

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

def get_channel(guild_id, game):
    """Get the channel ID for a specific game in a guild."""
    config = load_config()
    guild_key = str(guild_id)

    if guild_key not in config:
        return None

    return config[guild_key].get(game)