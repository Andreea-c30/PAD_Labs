#animal_posts_service/server.py
import grpc
import animal_posts_pb2
import animal_posts_pb2_grpc
from models import db, animal_posts
from flask import Flask
import time
import requests
import concurrent.futures
from prometheus_flask_exporter import PrometheusMetrics, NO_PREFIX
import threading
import redis
import json
from redis import Redis

# Initialize Redis client
try:
    redis_client = Redis(host='redis', port=6379)
    redis_client.ping()  # Test connection
    print("Successfully connected to Redis.")
except Exception as e:
    print(f"Failed to connect to Redis: {e}")
    redis_client = None

app = Flask(__name__)
app.config.from_object('config')
db.init_app(app)
# Connect Prometheus


metrics = PrometheusMetrics(app, defaults_prefix=NO_PREFIX)
metrics.info('app_info', 'Application info', version='1.0.3')
with app.app_context():
    db.create_all()


def register_service(service_name, service_url):
    try:
        requests.post("http://service_discovery:3001/register", json={
            "serviceName": service_name,
            "serviceUrl": service_url
        })
    except Exception as e:
        print(f"Failed to register service: {e}")


class AnimalService(animal_posts_pb2_grpc.AnimalPostServiceServicer):
    # run tasks with a timeout
    def run_with_timeout(self, task_func, timeout, *args, **kwargs):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(task_func, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError as e:
                print("Request timed out")
                return animal_posts_pb2.CreateAnimalResponse(postId=0, message="Request timed out after 5 seconds", status_code=408)
            except Exception as e:
                print(f"An error occurred: {e}")
                return animal_posts_pb2.CreateAnimalResponse(postId=0, message=f"An error occurred: {e}", status_code=500)


    # create a new animal post
    def CreateAnimalPost(self, request, context):
        def create_task():
            new_post = {
                "title": request.title,
                "description": request.description,
                "location": request.location,
                "status": request.status
            }

            with app.app_context():
                db.session.execute(animal_posts.insert().values(new_post))
                #time.sleep(10)
                db.session.commit()
                post_id = db.session.execute(animal_posts.select().order_by(animal_posts.c.id.desc())).fetchone()[0]

            redis_client.set("animals", '')
            return animal_posts_pb2.CreateAnimalResponse(postId=post_id, message="Post created successfully", status_code=200)

        return self.run_with_timeout(create_task, 5)


    # update an existing animal post
    def UpdateAnimalPost(self, request, context):
        def update_task():
            with app.app_context():
                post = db.session.execute(animal_posts.select().where(animal_posts.c.id == request.postId)).fetchone()
                if post is None:
                    context.set_details('Post not found')
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return animal_posts_pb2.UpdateAnimalResponse(message="Post not found", status_code=404)

                updated_post = {
                    "title": request.title,
                    "description": request.description,
                    "location": request.location,
                    "status": request.status
                }
                db.session.execute(animal_posts.update().where(animal_posts.c.id == request.postId).values(updated_post))
                db.session.commit()

            redis_client.set("animals", '')
            return animal_posts_pb2.UpdateAnimalResponse(message="Post updated successfully", status_code=200)

        return self.run_with_timeout(update_task, 5)


    # retrieve animal posts
    def GetAnimals(self, request, context):
        def get_animals_task():
            if animals := redis_client.get("animals"):
                return animal_posts_pb2.AnimalListResponse(posts=map(animal_posts_pb2.AnimalPost, json.loads(animals)), source="Redis")

            with app.app_context():
                posts = db.session.execute(animal_posts.select()).fetchall()
            animals = []
            animals_data = []
            for post in posts:
                animal = animal_posts_pb2.AnimalPost(
                    postId=post.id,
                    title=post.title,
                    description=post.description,
                    location=post.location,
                    status=post.status
                )
                animals.append(animal)
                animals_data.append(dict(
                    postId=post.id,
                    title=post.title,
                    description=post.description,
                    location=post.location,
                    status=post.status
                ))

            redis_client.set("animals", json.dumps(animals_data))
            return animal_posts_pb2.AnimalListResponse(posts=animals, source="Database")

        return self.run_with_timeout(get_animals_task, 5)


    # delete animal post
    def DeleteAnimalPost(self, request, context):
        def delete_task():
            with app.app_context():
                post = db.session.execute(animal_posts.select().where(animal_posts.c.id == request.postId)).fetchone()
                if post is None:
                    context.set_details('Post not found')
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return animal_posts_pb2.DeleteAnimalResponse(message="Post not found", status_code=404)

                db.session.execute(animal_posts.delete().where(animal_posts.c.id == request.postId))
                db.session.commit()

            redis_client.set("animals", None)
            return animal_posts_pb2.DeleteAnimalResponse(message="Post deleted successfully", status_code=200)

        return self.run_with_timeout(delete_task, 5)


    # check the status of the service
    def CheckStatus(self, request, context):
        def status_task():
            return animal_posts_pb2.StatusResponse(status="Service is running", status_code=200)

        return self.run_with_timeout(status_task, 5)

    
    def AdoptAnimal(self, request, context):
        def _():
            post = db.session.execute(animal_posts.select().where(animal_posts.c.id == request.postId, animal_posts.c.status == "available")).fetchone()
            if post is None:
                context.set_details('Post not found')
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return animal_posts_pb2.DeleteAnimalResponse(message="Post not found", status_code=404)
            
            db.session.execute(animal_posts.update().where(animal_posts.c.id == request.postId).values({"status": "unavailable"}))
            db.session.commit()

            return animal_posts_pb2.AdoptAnimalResponse(status="Animal adopted", status_code=200)

        return self.run_with_timeout(_, 5)

    
    # get load method implementation
    def GetLoad(self, request, context):
        def load_task():
            with app.app_context():
                total_posts = db.session.query(animal_posts).count()
            return animal_posts_pb2.LoadResponse(load=total_posts, status_code=200)

        return self.run_with_timeout(load_task, 5)

    transaction_store = {}

    def Prepare(self, request, context):
        try:
            payload = json.loads(request.payload)
            post_id = payload.get("postId")
            operation = request.operation

            # Check if the resource is already locked
            lock_key = f"lock:post:{post_id}"
            if redis_client.get(lock_key):
                context.set_code(grpc.StatusCode.ABORTED)
                return animal_posts_pb2.TransactionResponse(
                    transaction_id=request.transaction_id,
                    success=False,
                    message="Resource is locked for another transaction."
                )

            # Lock the resource for this transaction
            redis_client.set(lock_key, "locked", ex=60)  # Lock expires in 60 seconds

            with app.app_context():
                post = db.session.execute(
                    animal_posts.select().where(animal_posts.c.id == post_id)
                ).fetchone()
                if operation == "adopt" and (not post or post.status != "available"):
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                    return animal_posts_pb2.TransactionResponse(
                        transaction_id=request.transaction_id,
                        success=False,
                        message=f"Post {post_id} is not available for adoption."
                    )

            self.transaction_store[request.transaction_id] = {"state": "prepared", "payload": payload}
            return animal_posts_pb2.TransactionResponse(
                transaction_id=request.transaction_id,
                success=True,
                message="Prepare phase successful."
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            return animal_posts_pb2.TransactionResponse(
                transaction_id=request.transaction_id,
                success=False,
                message=f"Prepare phase failed: {str(e)}"
            )


    def Commit(self, request, context):
        """
        Commit phase: Finalize the transaction.
        """
        try:
            transaction = self.transaction_store.get(request.transaction_id)
            if not transaction or transaction["state"] != "prepared":
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                return animal_posts_pb2.TransactionResponse(
                    transaction_id=request.transaction_id,
                    success=False,
                    message="Transaction not in prepared state."
                )

            payload = transaction["payload"]
            post_id = payload.get("postId")
            operation = request.operation

            # Finalize the transaction (e.g., mark the animal as adopted)
            with app.app_context():
                if operation == "adopt":
                    db.session.execute(
                        animal_posts.update()
                        .where(animal_posts.c.id == post_id)
                        .values({"status": "unavailable"})
                    )
                    db.session.commit()

            # Mark the transaction as committed
            self.transaction_store[request.transaction_id]["state"] = "committed"
            return animal_posts_pb2.TransactionResponse(
                transaction_id=request.transaction_id,
                success=True,
                message="Commit phase successful."
            )

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            return animal_posts_pb2.TransactionResponse(
                transaction_id=request.transaction_id,
                success=False,
                message=f"Commit phase failed: {str(e)}"
            )

    def Rollback(self, request, context):
        try:
            transaction = self.transaction_store.get(request.transaction_id)
            if not transaction or transaction["state"] != "prepared":
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                return animal_posts_pb2.TransactionResponse(
                    transaction_id=request.transaction_id,
                    success=False,
                    message="Transaction not in prepared state or already committed."
                )

            payload = transaction["payload"]
            post_id = payload.get("postId")
            lock_key = f"lock:post:{post_id}"

            # Release the lock
            redis_client.delete(lock_key)

            # Mark the transaction as rolled back
            self.transaction_store[request.transaction_id]["state"] = "rolled_back"
            return animal_posts_pb2.TransactionResponse(
                transaction_id=request.transaction_id,
                success=True,
                message="Rollback phase successful."
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            return animal_posts_pb2.TransactionResponse(
                transaction_id=request.transaction_id,
                success=False,
                message=f"Rollback phase failed: {str(e)}"
            )


# start the gRPC server
def start_grpc_server():
    """Start the gRPC server."""
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=3))
    animal_posts_pb2_grpc.add_AnimalPostServiceServicer_to_server(AnimalService(), server)
    server.add_insecure_port('[::]:50052')
    print("gRPC server is running on port 50052")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    # Register the service in a service discovery mechanism
    register_service("AnimalService", "animal_posts_service:50052")
    
    # Run the gRPC server in a separate thread
    grpc_thread = threading.Thread(target=start_grpc_server, daemon=True)
    grpc_thread.start()

    # Start the Flask app for Prometheus metrics
    app.run(host="0.0.0.0", port=8000)
