import os
import json

def make_auth(username, password):
    """Create HTTP basic auth tuple"""
    return (username, password)

def ensure_dir(directory):
    """Ensure directory exists"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def load_mapping_config():
    """Load mapping configuration from file"""
    config_file = os.path.join('config', 'mapping_config.json')
    with open(config_file) as f:
        return json.load(f)

def map_user(email, mapping_config, default_user):
    """Map user email using configuration"""
    return mapping_config['users'].get(email, default_user)