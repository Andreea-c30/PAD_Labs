import grpc
from concurrent import futures
import time
import redis
import chat_pb2
import chat_pb2_grpc

# initialize redis client
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

class ChatServicer(chat_pb2_grpc.ChatServicer):
    def ChatStream(self, request_iterator, context):
        for request in request_iterator:
            print(f"Received message from {request.username}: {request.message}")
            
            #saving the message to redis
            redis_client.rpush("chat_messages", f"{request.username}: {request.message}")

            # yield a response immediately after saving the message
            yield chat_pb2.MessageResponse(response=f"Message  received!")
    #return the current status of the server   
    def GetStatus(self, request, context):
        return chat_pb2.StatusResponse(status="\nServer is running")
    
    #retrieve chat history from the Redis database
    def GetChatHistory(self, request, context):
        messages = redis_client.lrange("chat_messages", 0, -1)

        if messages:
            return chat_pb2.ChatHistoryResponse(messages=messages)
        else:
            return chat_pb2.ChatHistoryResponse(messages=[])


def start_serv():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    #adding the ChatServicer to the server
    chat_pb2_grpc.add_ChatServicer_to_server(ChatServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print(f"Server is running on port 50051 with a limit of {max_concurrent_tasks} concurrent tasks.")
    try:
        while True:
            time.sleep(86400) 
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    start_serv()
