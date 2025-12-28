import os
import subprocess
import requests
import json
import asyncio
import websockets
import signal
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

def register_with_server(server_url, group, name, public_key, external_ip, external_port):
    resp = requests.post(f'{server_url}/register', json={
        'group': group,
        'name': name,
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

def bring_up_interface():
    subprocess.run(['sudo', 'wg-quick', 'down', './wg0.conf'], check=False, capture_output=True)
    subprocess.run(['sudo', 'wg-quick', 'up', './wg0.conf'], check=True)
    print('WireGuard interface brought up successfully.')

def save_and_apply_config(config):
    with open('wg0.conf', 'w') as f:
        f.write(config)
    bring_up_interface()

def configs_equal(a, b):
    return a.strip() == b.strip()

def print_peer_table(peers, my_ip):
    print("\nCurrent group members:")
    print(f"{'Name':<20} {'Internal IP':<15} {'External IP':<15}")
    print("-"*55)
    for peer in peers:
        mark = '<- you' if peer['internal_ip'] == my_ip else ''
        print(f"{peer.get('name','(no name)'):<20} {peer['internal_ip']:<15} {peer['external_ip']:<15} {mark}")
    print()

async def peer_agent():
    server_url = input('Coord server URL (e.g. http://localhost:8000): ').strip()
    group = input('Group name: ').strip()
    name = input('Your name: ').strip()
    listen_port = int(input('WireGuard listen port (e.g. 54320): ').strip())
    priv, pub = generate_keys()
    ext_ip, ext_port = get_public_info()
    reg = register_with_server(server_url, group, name, pub, ext_ip, listen_port)
    internal_ip = reg['internal_ip']
    peers = reg['peers']
    config = generate_wg_config(priv, internal_ip, listen_port, peers)
    save_and_apply_config(config)
    print('Initial WireGuard config applied.')
    print_peer_table(peers, internal_ip)
    ws_url = server_url.replace('http', 'ws') + f'/ws/{group}'
    print(f'Connecting to WebSocket: {ws_url}')

    async def leave_group():
        try:
            requests.post(f'{server_url}/leave', json={"group": group, "public_key": pub})
        except Exception as e:
            print(f"Error leaving group: {e}")
        try:
            subprocess.run(['sudo', 'wg-quick', 'down', './wg0.conf'], check=False, capture_output=True)
            print('WireGuard interface brought down.')
        except Exception as e:
            print(f"Error bringing down WireGuard: {e}")

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # add_signal_handler may not be implemented on Windows
            pass

    try:
        while not stop_event.is_set():
            try:
                async with websockets.connect(ws_url) as ws:
                    async def ws_receiver():
                        async for msg in ws:
                            data = json.loads(msg)
                            if data.get('event') == 'peer_update':
                                new_peers = data['peers']
                                new_config = generate_wg_config(priv, internal_ip, listen_port, new_peers)
                                with open('wg0.conf', 'r') as f:
                                    current_config = f.read()
                                if not configs_equal(current_config, new_config):
                                    print('Peer list changed, updating config and reloading WireGuard...')
                                    save_and_apply_config(new_config)
                                print_peer_table(new_peers, internal_ip)

                    ws_task = asyncio.create_task(ws_receiver())
                    stop_task = asyncio.create_task(stop_event.wait())
                    done, pending = await asyncio.wait(
                        [ws_task, stop_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
                    if stop_event.is_set():
                        break
            except Exception as e:
                print(f'WebSocket error: {e}. Reconnecting in 5 seconds...')
                await asyncio.sleep(5)
    finally:
        await leave_group()
        print('Peer agent stopped and left group.')

if __name__ == '__main__':
    asyncio.run(peer_agent())
