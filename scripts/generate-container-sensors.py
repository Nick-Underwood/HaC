#!/usr/bin/env python3
"""
Generate Home Assistant template binary sensors for Docker containers.
This script queries Docker hosts and creates binary sensors based on container labels.
"""
import json
import os
import sys
import urllib.request
import yaml

# Docker hosts from environment variables
DOCKER_HOSTS = {
    'docker-critical': os.getenv('DOCKER_CRITICAL_HOST', 'http://localhost:2375'),
    'docker-noncritical': os.getenv('DOCKER_NONCRITICAL_HOST', 'http://localhost:2375')
}

def get_monitored_containers(docker_url):
    """Fetch containers with ha.monitor=true label from Docker API."""
    try:
        url = f"{docker_url}/containers/json?all=true"
        with urllib.request.urlopen(url, timeout=5) as response:
            containers = json.loads(response.read())

        # Filter for containers with ha.monitor=true
        monitored = []
        for container in containers:
            labels = container.get('Labels', {})
            if labels.get('ha.monitor') == 'true':
                name = container['Names'][0].lstrip('/')
                monitored.append({
                    'name': name,
                    'state': container['State'],
                    'status': container['Status'],
                    'image': container['Image'],
                    'category': labels.get('ha.category', 'unknown'),
                    'compose_file': labels.get('ha.compose-file', ''),
                    'service_name': labels.get('ha.service-name', name)
                })
        return monitored
    except Exception as e:
        print(f"Error fetching from {docker_url}: {e}", file=sys.stderr)
        return []

def generate_binary_sensors():
    """Generate binary sensor configuration for all monitored containers."""
    sensors = []

    for host_name, docker_url in DOCKER_HOSTS.items():
        containers = get_monitored_containers(docker_url)

        for container in containers:
            sensor = {
                'name': f"Docker {container['name'].replace('-', ' ').title()}",
                'unique_id': f"{host_name}_{container['name']}",
                'state': '{{ is_state("sensor.' + host_name.replace('-', '_') + '_containers_json", "' + container['name'] + '") }}',
                'device_class': 'connectivity',
                'attributes': {
                    'host': host_name,
                    'container_name': container['name'],
                    'category': container['category'],
                    'compose_file': container['compose_file'],
                    'service_name': container['service_name']
                }
            }
            sensors.append(sensor)

    return [{'binary_sensor': sensors}]

if __name__ == '__main__':
    config = generate_binary_sensors()
    print(yaml.dump(config, default_flow_style=False, sort_keys=False))
