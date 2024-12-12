#new_chat/server.py
import asyncio
import time
import websockets
from pymongo import MongoClient
import datetime
import requests
import json
import grpc
from prometheus_flask_exporter import PrometheusMetrics, NO_PREFIX
import animal_posts_pb2_grpc
import logging
from flask import Flask, request

logger = logging.getLogger(__name__)
from redis import Redis

# Initialize Redis client
try:
    redis_client = Redis(host='redis', port=6379)
    redis_client.ping()  # Test connection
    print("Successfully connected to Redis.")
except Exception as e:
    print(f"Failed to connect to Redis: {e}")
    redis_client = None

# MongoDB connection
# MongoDB connection
try:
    client = MongoClient("mongodb://mongo:27017/")
    db = client['chat_db']
    messages_collection = db['messages']
    # Test connection
    client.admin.command('ping')
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")

# Connect Prometheus
app = Flask(__name__)
metrics = PrometheusMetrics(app, defaults_prefix=NO_PREFIX)
metrics.info('app_info', 'Application info', version='1.0.3')
# Global variables
connected_clients = {}  # Each room will have a set of connected clients
client_rooms = {}  # Track the room each client is in
max_concurrent_tasks = 3
# Semaphore for limiting concurrent tasks
semaphore = asyncio.Semaphore(max_concurrent_tasks)

channel = grpc.insecure_channel('localhost:50052')
stub = animal_posts_pb2_grpc.AnimalPostServiceStub(channel)


# Register the chat service with a service discovery
def register_service(service_name, service_url):
    try:
        requests.post("http://service_discovery:3001/register", json={
            "serviceName": service_name,
            "serviceUrl": service_url
        })
    except Exception as e:
        print(f"Failed to register service: {e}")


async def handle_client(websocket):
    room_name = "lobby" 
    await join_room(websocket, room_name)  

    try:
        async for message in websocket:
            try:
                logger.info(message)
                data = json.loads(message)

                if data.get('action') == 'join_room':
                    new_room = data.get('room', 'lobby')
                    await join_room(websocket, new_room)
                    room_name = new_room  
                elif data.get('action') == 'get_history':
                    await send_chat_history(websocket, room_name)
                elif data.get('action') == 'adopt':
                    await handle_adopt(data, websocket, room_name)
                else:
                    await handle_chat_message(data, websocket, room_name)
            except json.JSONDecodeError:
                error_message = json.dumps({"error": "Invalid JSON format"})
                await websocket.send(error_message)
            except Exception as e:
                print(f"Error handling message: {e}")

    finally:
        await leave_room(websocket, room_name)
        print(f"Client disconnected: {websocket.remote_address}")


async def join_room(websocket, room_name):
    # Leave any current room
    current_room = client_rooms.get(websocket)

    if current_room:
        await leave_room(websocket, current_room)  # Ensure leaving current room

    # Join the specified room
    if room_name not in connected_clients:
        connected_clients[room_name] = set()
    connected_clients[room_name].add(websocket)
    client_rooms[websocket] = room_name  # Track which room the client is in

    # Notify other users in the room
    await broadcast_to_room(room_name, json.dumps({
        "system": f"A new user has joined the room: {room_name}"
    }))
    print(f"User joined room {room_name}")


async def leave_room(websocket, room_name):
    # Remove client from the specified room
    if room_name in connected_clients:
        connected_clients[room_name].discard(websocket)
        if not connected_clients[room_name]:
            del connected_clients[room_name]  # Clean up empty room

        # Notify others in the room
        await broadcast_to_room(room_name, json.dumps({
            "system": f"A user has left the room: {room_name}"
        }))

    # Remove the room from client tracking
    client_rooms.pop(websocket, None)

import uuid
async def handle_chat_message(data, websocket, room_name):
    try:
        logger.info(f"Received message data: {data}")
        message_id = data.get("message_id", str(uuid.uuid4()))  # Generate or use provided ID
        username = data.get('username')
        chat_message = data.get('message')

        if not username or not chat_message:
            raise ValueError("Both 'username' and 'message' fields are required.")

        # Save message to the database
        message_record = {
            "message_id": message_id,
            "username": username,
            "message": chat_message,
            "room": room_name,
            "timestamp": datetime.datetime.utcnow()
        }
        result = messages_collection.insert_one(message_record)
        logger.info(f"Inserted message with ID: {result.inserted_id} for room {room_name}")

        # Send confirmation back to WebSocket client
        confirmation_message = {
            "action": "message_saved",
            "message_id": message_id,
            "status": "success"
        }
        logger.info(f"Sending confirmation: {confirmation_message}")
        await websocket.send(json.dumps(confirmation_message))
    except Exception as e:
        logger.error(f"Error in handle_chat_message: {e}")
        error_message = {
            "action": "message_saved",
            "message_id": data.get("message_id"),
            "status": "failure",
            "error": str(e)
        }
        await websocket.send(json.dumps(error_message))





async def handle_adopt(data, websocket, room_name):
    username = data.get('username')
    animal_id = data.get('animal_id')

    async with client.start_session() as session:
        session.start_transaction()

        message_record = {
            "username": username,
            "message": 'adopt',
            "room": room_name,
            "timestamp": datetime.datetime.utcnow()
        }
        messages_collection.insert_one(message_record)
        try:
            response = stub.AdoptAnimal({"postId": animal_id})
            response.raise_for_status()
        except Exception as e:
            print(f"Error on adoption process: {e}")
            session.abort_transaction()
        else:
            session.commit_transaction()


async def broadcast_to_room(room_name, message):
    # Send a message to all clients in a specific room
    if room_name in connected_clients:
        tasks = []
        for client in connected_clients[room_name]:
            # Check if the client connection is still open
            tasks.append(
                asyncio.create_task(send_message_if_open(client, message))
            )
        await asyncio.gather(*tasks)


async def send_message_if_open(client, message):
    try:
        # Attempt to send a message, and ignore clients that have closed the connection
        await client.send(message)
    except websockets.exceptions.ConnectionClosed:
        # If the connection is closed, do nothing (or log if necessary)
        print(f"Connection closed for {client.remote_address}")


async def send_chat_history(websocket, room_name):
    try:
        # Set a timeout
        await asyncio.wait_for(retrieve_and_send_history(websocket, room_name), timeout=5.0)
    except asyncio.TimeoutError:
        print("Time out")
        await websocket.send(json.dumps({"error": "Could not retrieve chat history within the timeout"}))


async def retrieve_and_send_history(websocket, room_name):
    # Retrieve chat history from MongoDB for the specific room
    messages = list(messages_collection.find({"room": room_name}).sort("timestamp", 1))
    history = [{"username": message['username'], "message": message['message']} for message in messages]

    # Send the chat history back to the requesting client
    history_message = json.dumps({"action": "chat_history", "history": history})
    await websocket.send(history_message)


async def main():
    register_service("ChatService", "ws://new_chat:6789")
    async with websockets.serve(handle_client, "new_chat", 6789):
        print("WebSocket server running on ws://new_chat:6789")
        await asyncio.Future()


from threading import Thread


# Start Flask metrics server
@app.route("/metrics")
def metrics_endpoint():
    return metrics.generate_latest()

@app.route("/health", methods=["GET"])
def health_check():
    try:
        # Ping the MongoDB server
        client.admin.command('ping')
        return {"status": "success", "message": "Connected to MongoDB"}, 200
    except Exception as e:
        return {"status": "failure", "message": str(e)}, 500
@app.route("/inspect_messages")
def inspect_messages():
    try:
        messages = list(messages_collection.find({}).limit(10))  # Fetch up to 10 messages
        return {
            "count": len(messages),
            "messages": messages
        }, 200
    except Exception as e:
        return {"error": str(e)}, 500
@app.route("/add_test_message", methods=["POST"])
def add_test_message():
    try:
        # Create a test message
        test_message = {
            "username": "test_user",
            "message": "This is a test message",
            "room": "test_room",
            "timestamp": datetime.datetime.utcnow()
        }
        # Insert the message into the database
        result = messages_collection.insert_one(test_message)
        return {
            "status": "success",
            "message": "Test message added to database",
            "inserted_id": str(result.inserted_id)
        }, 201
    except Exception as e:
        return {"status": "failure", "message": str(e)}, 500

@app.route("/get_messages/<room_name>", methods=["GET"])
def get_messages(room_name):
    try:
        # Fetch messages for the given room from MongoDB
        messages = list(messages_collection.find({"room": room_name}).sort("timestamp", 1))
        formatted_messages = [
            {
                "username": message.get("username", ""),
                "message": message.get("message", ""),
                "timestamp": message.get("timestamp", "").isoformat()
            }
            for message in messages
        ]
        return {"status": "success", "messages": formatted_messages}, 200
    except Exception as e:
        return {"status": "failure", "error": str(e)}, 500


@app.route("/add_message", methods=["POST"])
def add_message():
    try:
        # Parse the JSON payload from the request
        data = request.json  # Correct the typo from 'requests.json' to 'request.json'
        if not data:
            return {"status": "failure", "message": "Invalid or missing JSON data"}, 400

        username = data.get("username")
        message = data.get("message")
        room = data.get("room", "lobby")  # Default to 'lobby' if no room is specified

        # Validate required fields
        if not username or not message:
            return {"status": "failure", "message": "Missing 'username' or 'message' field"}, 400

        # Create the message record
        message_record = {
            "username": username,
            "message": message,
            "room": room,
            "timestamp": datetime.datetime.utcnow()
        }

        # Insert the message into MongoDB
        result = messages_collection.insert_one(message_record)
        return {
            "status": "success",
            "message": "Message added to database",
            "inserted_id": str(result.inserted_id)
        }, 201
    except Exception as e:
        logger.error(f"Error in add_message: {e}")
        return {"status": "failure", "message": str(e)}, 500

@app.route('/prepare', methods=['POST'])
def prepare_transaction():
    try:
        data = request.json
        username = data['username']
        room = data['room']
        message = data['message']

        # Log the incoming request
        print(f"Prepare request received: {data}")

        # Validate the room exists
        if not messages_collection.find_one({"room": room}):
            return {"status": "not ready", "reason": "Room does not exist"}, 400

        # Lock the room
        redis_client.set(f"lock:room:{room}", "locked")
        return {"status": "ready"}, 200
    except Exception as e:
        print(f"Error in prepare: {e}")
        return {"status": "not ready", "reason": str(e)}, 500


@app.route('/commit', methods=['POST'])
def commit_transaction():
    try:
        data = request.json
        username = data['username']
        room = data['room']
        message = data['message']

        # Save the message
        message_record = {
            "username": username,
            "message": message,
            "room": room,
            "timestamp": datetime.datetime.utcnow()
        }
        messages_collection.insert_one(message_record)

        # Release lock
        redis_client.delete(f"lock:room:{room}")
        return {"status": "committed"}, 200
    except Exception as e:
        return {"status": "failed", "reason": str(e)}, 500


@app.route('/rollback', methods=['POST'])
def rollback_transaction():
    try:
        data = request.json
        room = data.get('room')
        if not room:
            return {"status": "failed", "reason": "Missing 'room' parameter"}, 400

        print(f"Rollback request received for room: {room}")

        # Release lock
        redis_client.delete(f"lock:room:{room}")
        print(f"Lock released for room: {room}")

        return {"status": "rolled back"}, 200
    except Exception as e:
        print(f"Error in rollback: {e}")
        return {"status": "failed", "reason": str(e)}, 500


def start_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


if __name__ == "__main__":
    try:
        # Start WebSocket server in a separate thread
        websocket_thread = Thread(target=start_websocket_server)
        websocket_thread.start()

        # Start Flask app for Prometheus metrics
        app.run(host="0.0.0.0", port=9100)
    except KeyboardInterrupt:
        print("Server is shutting down...")
