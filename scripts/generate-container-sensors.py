#!/usr/bin/env python3
"""
Generate Home Assistant template binary sensors for Docker containers.
This script queries Docker hosts and creates binary sensors based on container labels.
"""
import json
import os
import sys
import urllib.request

try:
    import http.client
    import socket as _socket
except ImportError:  # pragma: no cover
    http = None

# Docker hosts from environment variables.
# Default to the local Docker socket (no TCP proxy needed). Set DOCKER_*_HOST to
# override, e.g. unix:///var/run/docker.sock or http://remote:2375.
_DFLT = os.getenv('DOCKER_HOST', 'unix:///var/run/docker.sock')
DOCKER_HOSTS = {
    '<REDACTED_HOST>': os.getenv('DOCKER_CRITICAL_HOST', _DFLT),
    '<REDACTED_HOST>': os.getenv('DOCKER_NONCRITICAL_HOST', _DFLT)
}


def _http_get_unix(socket_path, path):
    """Minimal HTTP/1.1 GET over a unix socket (no external deps)."""
    client = http.client.HTTPConnection('localhost', timeout=5)
    client.sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    client.sock.connect(socket_path)
    client.request('GET', path)
    resp = client.getresponse()
    data = resp.read().decode('utf-8')
    client.close()
    return json.loads(data)


def get_monitored_containers(docker_url):
    """Fetch containers with ha.monitor=true label from Docker API."""
    try:
        if docker_url.startswith('unix://'):
            path = '/containers/json?all=true'
            return _parse_containers(_http_get_unix(docker_url[len('unix://'):], path))
        url = f"{docker_url}/containers/json?all=true"
        with urllib.request.urlopen(url, timeout=5) as response:
            containers = json.loads(response.read())
        return _parse_containers(containers)
    except Exception as e:
        print(f"Error fetching from {docker_url}: {e}", file=sys.stderr)
        return []


def _parse_containers(containers):
    """Filter raw container list to those labeled ha.monitor=true."""
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
    import yaml
    config = generate_binary_sensors()
    print(yaml.dump(config, default_flow_style=False, sort_keys=False))
