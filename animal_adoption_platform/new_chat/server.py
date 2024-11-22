import asyncio
import time
import websockets
from pymongo import MongoClient
import datetime
import requests
import json
from flask import Flask
from prometheus_flask_exporter import PrometheusMetrics, NO_PREFIX
from threading import Thread

# MongoDB connection
client = MongoClient("mongodb://mongo:27017/")
db = client['chat_db']
messages_collection = db['messages']

# Connect Prometheus
app = Flask(__name__)
metrics = PrometheusMetrics(app, defaults_prefix=NO_PREFIX)
metrics.info('app_info', 'Application info', version='1.0.3')

# Global variables
connected_clients = {}  # Each room will have a set of connected clients
client_rooms = {}  # Track the room each client is in
max_concurrent_tasks = 3
semaphore = asyncio.Semaphore(max_concurrent_tasks)

# Register the chat service with service discovery
def register_service(service_name, service_url):
    try:
        requests.post("http://service_discovery:3001/register", json={
            "serviceName": service_name,
            "serviceUrl": service_url
        })
        print(f"Service {service_name} registered successfully.")
    except Exception as e:
        print(f"Failed to register service: {e}")

# Two-Phase Commit Preparation
async def prepare_adoption(post_id, username, chat_message):
    try:
        # Phase 1: Prepare - Animal Post Service should prepare the adoption
        animal_post_service_url = "http://animal_post_service:50052"
        response = await asyncio.to_thread(requests.post, f"{animal_post_service_url}/prepare_adoption", json={
            "postId": post_id,
            "username": username
        })

        if response.status_code != 200:
            print(f"Animal Post Service failed to prepare adoption for post {post_id}")
            return False

        # Phase 2: Commit - Send adoption confirmation message to Chat Service
        chat_message_data = {
            "username": username,
            "message": chat_message,
            "room": "adopt-room"  # Chat room for adoption-related messages
        }
        await send_adopt_message_to_chat(chat_message_data)
        return True

    except Exception as e:
        print(f"Error in prepare_adoption phase: {e}")
        return False

# Commit Adoption (send chat message)
async def send_adopt_message_to_chat(chat_message_data):
    try:
        async with websockets.connect("ws://new_chat:6789") as websocket:
            await websocket.send(json.dumps({
                "action": "send_message",
                "username": chat_message_data["username"],
                "message": chat_message_data["message"],
                "room": chat_message_data["room"]
            }))
            print(f"Adoption message sent to room {chat_message_data['room']}")
    except Exception as e:
        print(f"Error sending adoption message: {e}")

# Handle WebSocket Client Connection
async def handle_client(websocket):
    room_name = "lobby"  # Default room
    await join_room(websocket, room_name)

    try:
        async for message in websocket:
            try:
                data = json.loads(message)

                if data.get('action') == 'join_room':
                    new_room = data.get('room', 'lobby')
                    await join_room(websocket, new_room)
                    room_name = new_room
                elif data.get('action') == 'get_history':
                    await send_chat_history(websocket, room_name)
                elif data.get('action') == 'adopt':
                    post_id = data.get('postId')
                    username = data.get('username')
                    chat_message = f"User {username} has adopted the animal post {post_id}."
                    # Prepare the adoption using 2PC
                    success = await prepare_adoption(post_id, username, chat_message)
                    response = {"message": f"Post {post_id} adopted successfully!"} if success else {"error": "Failed to adopt post. Please try again."}
                    await websocket.send(json.dumps(response))
            except json.JSONDecodeError:
                error_message = json.dumps({"error": "Invalid JSON format"})
                await websocket.send(error_message)
            except Exception as e:
                print(f"Error handling message: {e}")

    except websockets.exceptions.ConnectionClosed:
        print("WebSocket connection closed.")
    finally:
        await leave_room(websocket, room_name)

# Helper Functions for Rooms, History, and Broadcasting

# Join Room
async def join_room(websocket, room_name):
    current_room = client_rooms.get(websocket)

    if current_room:
        await leave_room(websocket, current_room)

    if room_name not in connected_clients:
        connected_clients[room_name] = set()
    connected_clients[room_name].add(websocket)
    client_rooms[websocket] = room_name

    await broadcast_to_room(room_name, json.dumps({
        "system": f"A new user has joined the room: {room_name}"
    }))
    print(f"User joined room {room_name}")

# Leave Room
async def leave_room(websocket, room_name):
    if room_name in connected_clients:
        connected_clients[room_name].discard(websocket)
        if not connected_clients[room_name]:
            del connected_clients[room_name]
        await broadcast_to_room(room_name, json.dumps({
            "system": f"A user has left the room: {room_name}"
        }))
    client_rooms.pop(websocket, None)

# Broadcast Message
async def broadcast_to_room(room_name, message):
    if room_name in connected_clients:
        tasks = []
        for client in connected_clients[room_name]:
            tasks.append(asyncio.create_task(send_message_if_open(client, message)))
        await asyncio.gather(*tasks)

async def send_message_if_open(client, message):
    try:
        await client.send(message)
    except websockets.exceptions.ConnectionClosed:
        print(f"Connection closed for client.")

# Send Chat History
async def send_chat_history(websocket, room_name):
    try:
        await asyncio.wait_for(retrieve_and_send_history(websocket, room_name), timeout=5.0)
    except asyncio.TimeoutError:
        print("Timeout")
        await websocket.send(json.dumps({"error": "Could not retrieve chat history within the timeout"}))

async def retrieve_and_send_history(websocket, room_name):
    messages = list(messages_collection.find({"room": room_name}).sort("timestamp", 1))
    history = [{"username": message['username'], "message": message['message']} for message in messages]
    history_message = json.dumps({"action": "chat_history", "history": history})
    await websocket.send(history_message)

# Start WebSocket Server
async def main():
    register_service("ChatService", "ws://new_chat:6789")
    async with websockets.serve(handle_client, "0.0.0.0", 6789):
        print("WebSocket server running on ws://new_chat:6789")
        await asyncio.Future()  # Run forever

# Flask Metrics
@app.route("/metrics")
def metrics_endpoint():
    return metrics.generate_latest()

# Start WebSocket Server in Separate Thread
def start_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

if __name__ == "__main__":
    try:
        websocket_thread = Thread(target=start_websocket_server, daemon=True)
        websocket_thread.start()
        app.run(host="0.0.0.0", port=9100)
    except KeyboardInterrupt:
        print("Server is shutting down...")
