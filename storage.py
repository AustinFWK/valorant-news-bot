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

def set_channel(server_id, game, channel_id):
    """Set the channel ID for a specific game in a server."""
    config = load_config()

    #set server id if not present
    server_key = str(server_id)
    if server_key not in config:
        config[server_key] = {}
    
    config[server_key][game] = channel_id
    save_config(config)

def get_channel(server_id, game):
    """Get the channel ID for a specific game in a server."""
    config = load_config()
    server_key = str(server_id)

    if server_key not in config:
        return None

    return config[server_key].get(game)