#!/bin/bash
# Custom NetBox entrypoint to install plugins before starting

set -e

# Install plugins from plugin_requirements.txt if it exists
if [ -f /opt/netbox/plugin_requirements.txt ]; then
    echo "Installing NetBox plugins..."
    # Use system python3 pip (venv pip is isolated, use /usr/bin/python3 -m pip)
    if ! /usr/bin/python3 -m pip --version >/dev/null 2>&1; then
        echo "Installing system python3-pip..."
        if command -v apt-get >/dev/null 2>&1; then
            apt-get update && apt-get install -y python3-pip || true
        elif command -v apk >/dev/null 2>&1; then
            apk add --no-cache py3-pip || true
        fi
    fi
    # Install plugins using system python3 pip
    /usr/bin/python3 -m pip install --no-warn-script-location -r /opt/netbox/plugin_requirements.txt || true
fi

# Run the original entrypoint
exec /opt/netbox/docker-entrypoint.sh "$@"
