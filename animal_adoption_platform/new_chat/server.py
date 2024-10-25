import asyncio
import time
import websockets
from pymongo import MongoClient
import datetime
import requests
import json

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client['chat_db']
messages_collection = db['messages']

connected_clients = set()
max_concurrent_tasks = 3
# Semaphore for limiting concurrent tasks
semaphore = asyncio.Semaphore(max_concurrent_tasks)

def register_service(service_name, service_url):
    try:
        requests.post("http://localhost:3001/register", json={
            "serviceName": service_name,
            "serviceUrl": service_url
        })
    except Exception as e:
        print(f"Failed to register service: {e}")

async def handle_client(websocket, path):
    # register the new client
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            try:
                # parse the received message as JSON
                data = json.loads(message)

                # check if the message is a request for chat history
                if data.get('action') == 'get_history':
                    await send_chat_history(websocket)
                else:
                    await handle_chat_message(data, websocket)
            except json.JSONDecodeError:
                error_message = json.dumps({"error": "Invalid JSON format"})
                await websocket.send(error_message)
            except Exception as e:
                print(f"Error handling message: {e}")

    finally:
        # unregister the client
        connected_clients.remove(websocket)
        print(f"Client disconnected: {websocket.remote_address}")

async def handle_chat_message(data, websocket):
    # limit concurrent execution
    async with semaphore:
        try:
            # extract username and message from the received data
            username = data.get('username')
            chat_message = data.get('message')

            if username and chat_message:
                # log the received message with username
                client_info = f"{websocket.remote_address}"
                print(f"Received message from {username} ({client_info}): {chat_message}")

                # save the message to MongoDB
                message_record = {
                    "username": username,
                    "message": chat_message,
                    "timestamp": datetime.datetime.utcnow()
                }
                # store the message in MongoDB
                messages_collection.insert_one(message_record)

                # prepare broadcast message
                broadcast_message = json.dumps({"username": username, "message": chat_message})

                # broadcast the message to all connected clients
                await asyncio.gather(*[client.send(broadcast_message) for client in connected_clients if client.open])
        except Exception as e:
            print(f"Error saving message or sending broadcast: {e}")

async def send_chat_history(websocket):
    try:
        # set a timeout
        await asyncio.wait_for(retrieve_and_send_history(websocket), timeout=5.0)
    except asyncio.TimeoutError:
        print("Time out")
        await websocket.send(json.dumps({"error": "Could not retrieve chat history within the timeout"}))

async def retrieve_and_send_history(websocket):
    # retrieve chat history from MongoDB
    messages = messages_collection.find().sort("timestamp", 1)
    history = []

    # fetch messages into the history list
    async for message in messages:
        history.append({
            "username": message['username'],
            "message": message['message']
        })

    # send the chat history back to the requesting client
    history_message = json.dumps({"action": "chat_history", "history": history})
    await websocket.send(history_message)

async def main():
    register_service("ChatService", "ws://localhost:6789")
    # handle multiple clients concurrently by creating a task for each connection
    async with websockets.serve(handle_client, "localhost", 6789):
        print("WebSocket server running on ws://localhost:6789")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server is shutting down...")
