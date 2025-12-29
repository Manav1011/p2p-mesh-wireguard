import asyncio
import sys
from aiortc import RTCPeerConnection, RTCSessionDescription

async def run():
    pc = RTCPeerConnection()

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is", pc.connectionState)
        if pc.connectionState == "connected":
            print("Peers are connected!")
        elif pc.connectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            print("Connection closed.")

    # Data channel for testing
    async def send_pings(channel, label):
        count = 0
        while True:
            await asyncio.sleep(2)
            msg = f"ping {count} from {label}"
            channel.send(msg)
            print(f"[Sent] {msg}")
            count += 1

    if len(sys.argv) > 1 and sys.argv[1] == "offer":
        channel = pc.createDataChannel("chat")
        @channel.on("open")
        def on_open():
            print("Data channel is open!")
            channel.send("Hello from offerer!")
            asyncio.create_task(send_pings(channel, "offerer"))
        @channel.on("message")
        def on_message(message):
            print("[Received]", message)
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        print("\n=== Paste this offer to the other peer ===\n")
        print(pc.localDescription.sdp)
        print("\n=== End offer ===\n")
        print("Paste the answer SDP:")
        answer_sdp = sys.stdin.read()
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await pc.setRemoteDescription(answer)
    else:
        print("Paste the offer SDP:")
        offer_sdp = sys.stdin.read()
        print(offer_sdp)
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        print("\n=== Paste this answer to the offer peer ===\n")
        print(pc.localDescription.sdp)
        print("\n=== End answer ===\n")
        @pc.on("datachannel")
        def on_datachannel(channel):
            @channel.on("open")
            def on_open():
                print("Data channel is open!")
                channel.send("Hello from answerer!")
                asyncio.create_task(send_pings(channel, "answerer"))
            @channel.on("message")
            def on_message(message):
                print("[Received]", message)
    # Keep the event loop running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run())
