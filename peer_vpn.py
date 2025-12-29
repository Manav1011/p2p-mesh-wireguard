


import stun
from pytun import TunTapDevice, IFF_TUN, IFF_NO_PI
import os
import fcntl
import socket
import threading
import json
import time
import sys
nat_type, external_ip, external_port = stun.get_ip_info(stun_host='stun.l.google.com', stun_port=19302)



# CONFIGURE THESE (set for both peers, select at runtime)
PEER_CONFIGS = {
    "peer1": {
        "MY_PORT": 54320,
        "PEER_IP": "49.36.117.229",  # peer1's public IP
        "PEER_PORT": 54320,
        "MY_VPN_IP": "10.8.0.1",
        "PEER_VPN_IP": "10.8.0.2",
    },
    "peer2": {
        "MY_PORT": 54320,
        "PEER_IP": "110.226.96.28",  # peer2's public IP
        "PEER_PORT": 54320,
        "MY_VPN_IP": "10.8.0.2",
        "PEER_VPN_IP": "10.8.0.1",
    }
}
VPN_NETMASK = '255.255.255.0'


def is_valid_ip_packet(data):
    # Basic check: IPv4 header is at least 20 bytes, first nibble is 4
    if len(data) < 20:
        return False
    first_byte = data[0]
    version = first_byte >> 4
    return version == 4



def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PEER_CONFIGS:
        print("Usage: sudo python peer_vpn.py [peer1|peer2]")
        sys.exit(1)
    peer = sys.argv[1]
    config = PEER_CONFIGS[peer]

    nat_type, external_ip, external_port = stun.get_ip_info(stun_host='stun.l.google.com', stun_port=19302)
    print(f"NAT Type: {nat_type}")
    print(f"External IP: {external_ip}")
    print(f"External Port: {external_port}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', config["MY_PORT"]))


    # Set up TUN device
    def setup_tun():
        tun = TunTapDevice(flags=IFF_TUN | IFF_NO_PI)
        tun.addr = config["MY_VPN_IP"]
        tun.dstaddr = config["PEER_VPN_IP"]
        tun.netmask = VPN_NETMASK
        tun.mtu = 1400
        tun.up()
        print(f"TUN device {tun.name} set up with IP {config['MY_VPN_IP']}")
        return tun



    # Listen for UDP packets and write to TUN if it's a VPN packet
    def udp_listener(tun):
        while True:
            data, addr = sock.recvfrom(4096)
            # Try to decode as control message
            try:
                message = json.loads(data.decode())
                print(f"[RECV] From {addr}: {message}")
                if message.get("type") == "ping":
                    response = {
                        "type": "pong",
                        "timestamp": time.time(),
                        "from": peer
                    }
                    sock.sendto(json.dumps(response).encode(), (config["PEER_IP"], config["PEER_PORT"]))
            except Exception:
                # Not a control message, treat as VPN packet
                if is_valid_ip_packet(data):
                    try:
                        tun.write(data)
                    except Exception as e:
                        print(f"[TUN WRITE ERROR] {e}")
                else:
                    print(f"[DROP] Non-IP packet received from {addr}, length={len(data)}")



    def tun_reader(tun):
        while True:
            try:
                packet = tun.read(tun.mtu)
                # Send raw IP packet to peer
                sock.sendto(packet, (config["PEER_IP"], config["PEER_PORT"]))
            except Exception as e:
                print(f"[TUN READ ERROR] {e}")


    tun = setup_tun()

    # Start UDP listener (for both control and VPN packets)
    threading.Thread(target=udp_listener, args=(tun,), daemon=True).start()
    # Start TUN reader (to send VPN packets)
    threading.Thread(target=tun_reader, args=(tun,), daemon=True).start()

    # Optionally, send an initial ping to peer to open NAT
    # message = {
    #     "type": "ping",
    #     "timestamp": time.time(),
    #     "from": peer
    # }
    # sock.sendto(json.dumps(message).encode(), (config["PEER_IP"], config["PEER_PORT"]))

    # Keep process alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
