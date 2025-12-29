import socket
import threading
import time

MY_PORT = 54320

# Replace these with the OTHER machine's public IP
PEER_IP = input("Enter peer public IP: ").strip()
PEER_PORT = 54320

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", MY_PORT))

print(f"Listening on 0.0.0.0:{MY_PORT}")

def listen():
    while True:
        data, addr = sock.recvfrom(2048)
        print(f"\n[RECEIVED] {data.decode()} from {addr}")

threading.Thread(target=listen, daemon=True).start()

# Give listener time to start
time.sleep(1)

print("Sending punch packets...")

while True:
    msg = "PING"
    sock.sendto(msg.encode(), (PEER_IP, PEER_PORT))
    print("Sent:", msg)
    time.sleep(1)
