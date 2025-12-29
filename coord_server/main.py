
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import uuid

app = FastAPI()
@app.post("/leave")
async def leave_peer(group: str = Body(...), public_key: str = Body(...)):
    if group in groups:
        remove_id = None
        for pid, pinfo in groups[group].items():
            if pinfo['public_key'] == public_key:
                remove_id = pid
                break
        if remove_id:
            del groups[group][remove_id]
            # Notify via websocket
            for ws in ws_connections[group]:
                await ws.send_json({"event": "peer_update", "peers": list(groups[group].values())})
            return {"status": "left"}
    return JSONResponse(status_code=404, content={"error": "Peer not found in group"})

groups: Dict[str, Dict[str, dict]] = {}  # group_name -> peer_id -> peer_info
ws_connections: Dict[str, List[WebSocket]] = {}  # group_name -> list of websockets

class PeerRegister(BaseModel):
    group: str
    name: str
    public_key: str
    external_ip: str
    external_port: int

class PeerInfo(BaseModel):
    peer_id: str
    name: str
    public_key: str
    internal_ip: str
    external_ip: str
    external_port: int

@app.post("/register")
async def register_peer(peer: PeerRegister):
    group = peer.group
    if group not in groups:
        groups[group] = {}
        ws_connections[group] = []

    # Uniqueness: public_key + external_ip + external_port
    existing_peer_id = None
    for pid, pinfo in groups[group].items():
        if (
            pinfo['public_key'] == peer.public_key and
            pinfo['external_ip'] == peer.external_ip and
            pinfo['external_port'] == peer.external_port
        ):
            existing_peer_id = pid
            break

    if existing_peer_id:
        # Update existing peer
        groups[group][existing_peer_id]["name"] = peer.name
        # Optionally update external_ip/port if changed
        groups[group][existing_peer_id]["external_ip"] = peer.external_ip
        groups[group][existing_peer_id]["external_port"] = peer.external_port
        peer_id = existing_peer_id
        internal_ip = groups[group][existing_peer_id]["internal_ip"]
    else:
        # Assign internal IP (simple: 10.0.0.x/24)
        used_ips = {info['internal_ip'] for info in groups[group].values()}
        for i in range(2, 255):
            ip = f"10.0.0.{i}"
            if ip not in used_ips:
                internal_ip = ip
                break
        else:
            return JSONResponse(status_code=400, content={"error": "No IPs available"})
        peer_id = str(uuid.uuid4())
        peer_info = {
            "peer_id": peer_id,
            "name": peer.name,
            "public_key": peer.public_key,
            "internal_ip": internal_ip,
            "external_ip": peer.external_ip,
            "external_port": peer.external_port
        }
        groups[group][peer_id] = peer_info

    # Notify via websocket
    for ws in ws_connections[group]:
        await ws.send_json({"event": "peer_update", "peers": list(groups[group].values())})
    return {"peer_id": peer_id, "internal_ip": internal_ip, "peers": list(groups[group].values())}

@app.post("/update")
async def update_peer(peer_id: str, group: str, external_ip: str, external_port: int):
    if group in groups and peer_id in groups[group]:
        groups[group][peer_id]["external_ip"] = external_ip
        groups[group][peer_id]["external_port"] = external_port
        # Notify via websocket
        for ws in ws_connections[group]:
            await ws.send_json({"event": "peer_update", "peers": list(groups[group].values())})
        return {"status": "updated"}
    return JSONResponse(status_code=404, content={"error": "Peer not found"})

@app.get("/peers/{group}")
async def get_peers(group: str):
    if group in groups:
        return list(groups[group].values())
    return []

@app.websocket("/ws/{group}")
async def websocket_endpoint(websocket: WebSocket, group: str):
    await websocket.accept()
    if group not in ws_connections:
        ws_connections[group] = []
    ws_connections[group].append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_connections[group].remove(websocket)
