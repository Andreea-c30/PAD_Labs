import redis

def get_chat_history():
    redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
    messages = redis_client.lrange("chat_messages", 0, -1)
    if messages:
        print("Chat History:")
        for message in messages:
            print(message)
    else:
        print("No messages found.")

if __name__ == '__main__':
    get_chat_history()
