import grpc
import chat_pb2
import chat_pb2_grpc

def generate_messages(username):
    #yield chat messages from the user
    while True:
        message = input(f"{username}, enter your message: ")
        yield chat_pb2.MessageRequest(username=username, message=message)

def get_status(stub):
    #fetch and print the server status
    try:
        response = stub.GetStatus(chat_pb2.Empty())
        print(f"Server Status: {response.status}")
    except grpc.RpcError as e:
        print(f"Error getting status: {e.details()}")

def run():
    #start the client and handle chat streaming
    channel = grpc.insecure_channel('localhost:50051')
    stub = chat_pb2_grpc.ChatStub(channel)
    username = input("Enter your username: ")
    get_status(stub)

    try:
        # start streaming chat messages
        responses = stub.ChatStream(generate_messages(username))
        # listen for responses from the server
        for response in responses:
            print(f"Server response: {response.response}")
    except grpc.RpcError as e:
        print(f"Error in ChatStream: {e.details()}")

if __name__ == '__main__':
    run()
