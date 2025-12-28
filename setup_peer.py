import os
import subprocess
import requests
import json
from discovery import get_public_info

def generate_keys():
    if not os.path.exists('privatekey'):
        priv = subprocess.check_output(['wg', 'genkey']).decode().strip()
        with open('privatekey', 'w') as f:
            f.write(priv)
        pub = subprocess.check_output(['wg', 'pubkey'], input=priv.encode()).decode().strip()
        with open('publickey', 'w') as f:
            f.write(pub)
    else:
        with open('privatekey') as f:
            priv = f.read().strip()
        with open('publickey') as f:
            pub = f.read().strip()
    return priv, pub

def register_with_server(server_url, group, public_key, external_ip, external_port):
    resp = requests.post(f'{server_url}/register', json={
        'group': group,
        'public_key': public_key,
        'external_ip': external_ip,
        'external_port': external_port
    })
    resp.raise_for_status()
    return resp.json()

def fetch_peers(server_url, group):
    resp = requests.get(f'{server_url}/peers/{group}')
    resp.raise_for_status()
    return resp.json()

def generate_wg_config(private_key, internal_ip, listen_port, peers):
    config = [
        '[Interface]',
        f'PrivateKey = {private_key}',
        f'Address = {internal_ip}/24',
        f'ListenPort = {listen_port}',
        ''
    ]
    for peer in peers:
        if peer['internal_ip'] == internal_ip:
            continue
        config += [
            '[Peer]',
            f'PublicKey = {peer["public_key"]}',
            f'AllowedIPs = {peer["internal_ip"]}/32',
            f'Endpoint = {peer["external_ip"]}:{peer["external_port"]}',
            'PersistentKeepalive = 25',
            ''
        ]
    return '\n'.join(config)

def main():
    server_url = input('Coord server URL (e.g. http://localhost:8000): ').strip()
    group = input('Group name: ').strip()
    listen_port = int(input('WireGuard listen port (e.g. 54320): ').strip())
    priv, pub = generate_keys()
    ext_ip, ext_port = get_public_info()
    reg = register_with_server(server_url, group, pub, ext_ip, listen_port)
    internal_ip = reg['internal_ip']
    peers = reg['peers']
    config = generate_wg_config(priv, internal_ip, listen_port, peers)
    with open('wg0.conf', 'w') as f:
        f.write(config)
    print('WireGuard config written to wg0.conf')
    print('Peers:', json.dumps(peers, indent=2))
    # Bring up the WireGuard interface automatically
    try:
        subprocess.run(['sudo', 'wg-quick', 'down', './wg0.conf'], check=False, capture_output=True)
        subprocess.run(['sudo', 'wg-quick', 'up', './wg0.conf'], check=True)
        print('WireGuard interface brought up successfully.')
    except Exception as e:
        print(f'Error bringing up WireGuard interface: {e}')


main()
import subprocess
import os

def generate_keys():
    """Generates WireGuard Private and Public keys."""
    # We use subprocess to call the 'wg' command
    priv_key = subprocess.check_output(["wg", "genkey"]).decode("utf-8").strip()
    pub_key = subprocess.check_output(["wg", "pubkey"], input=priv_key.encode()).decode("utf-8").strip()
    return priv_key, pub_key

def create_config(my_private_key, my_ip, my_port, peer_public_key, peer_endpoint, peer_internal_ip):
    """Generates a WireGuard config string."""
    config = f"""
[Interface]
PrivateKey = {my_private_key}
Address = {my_ip}/24
ListenPort = {my_port}

[Peer]
PublicKey = {peer_public_key}
Endpoint = {peer_endpoint}
AllowedIPs = {peer_internal_ip}/32
PersistentKeepalive = 25
"""
    return config

# Check if 'wg' tool is installed
try:
    subprocess.run(["wg", "--version"], check=True, capture_output=True)
except Exception:
    print("Error: WireGuard (wg) tools are not installed.")
    exit(1)

print("--- Peer Setup Helper ---")
priv, pub = generate_keys()
print(f"YOUR Public Key: {pub}")
print(f"YOUR Private Key: {priv} (SAVE THIS SECRET!)")
    
    # In a real app, you would send 'pub' to your server here
    # and receive the data for 'peer_public_key' and 'peer_endpoint'
