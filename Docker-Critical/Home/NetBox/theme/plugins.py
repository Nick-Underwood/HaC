# NetBox Plugins Configuration
# Add plugin names here after installing in plugin_requirements.txt
# Note: plugin name for pip may differ from the config name (use underscore, not hyphen)

PLUGINS = [
    'netbox_secrets',
    # 'netbox_inventory',
]

PLUGINS_CONFIG = {
    # Plugin-specific settings go here
    # Example:
    # 'netbox_secrets': {
    #     'setting_name': 'value',
    # },
}

