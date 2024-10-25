import grpc
import animal_posts_pb2
import animal_posts_pb2_grpc
from models import db, animal_posts
from flask import Flask
import time
import requests
import concurrent.futures

app = Flask(__name__)
app.config.from_object('config')
db.init_app(app)

with app.app_context():
    db.create_all()

def register_service(service_name, service_url):
    try:
        requests.post("http://localhost:3001/register", json={
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
            except concurrent.futures.TimeoutError:
                print("Request timed out")
                return animal_posts_pb2.CreateAnimalResponse(postId=0, message="Request timed out after 5 seconds", status_code=408)
            except Exception as e:
                print(f"An error occurred: {e}")
                return animal_posts_pb2.CreateAnimalResponse(postId=0, message="An error occurred", status_code=500)

    # create a new animal post
    def CreateAnimalPost(self, request, context):
        def create_task():
            new_post = {
                "title": request.title,
                "description": request.description,
                "location": request.location,
                "status": request.status,
                "images": request.images
            }
            time.sleep(10)
            with app.app_context():
                db.session.execute(animal_posts.insert().values(new_post))
                db.session.commit()
                post_id = db.session.execute(animal_posts.select().order_by(animal_posts.c.id.desc())).fetchone()[0]

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
                    "status": request.status,
                    "images": request.images
                }
                db.session.execute(animal_posts.update().where(animal_posts.c.id == request.postId).values(updated_post))
                db.session.commit()

            return animal_posts_pb2.UpdateAnimalResponse(message="Post updated successfully", status_code=200)

        return self.run_with_timeout(update_task, 5)

    # retrieve animal posts
    def GetAnimals(self, request, context):
        def get_animals_task():
            with app.app_context():
                posts = db.session.execute(animal_posts.select()).fetchall()
            animals = []
            for post in posts:
                animal = animal_posts_pb2.AnimalPost(
                    postId=post.id,
                    title=post.title,
                    description=post.description,
                    location=post.location,
                    status=post.status,
                    images=post.images
                )
                animals.append(animal)

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

            return animal_posts_pb2.DeleteAnimalResponse(message="Post deleted successfully", status_code=200)

        return self.run_with_timeout(delete_task, 5)

    # check the status of the service
    def CheckStatus(self, request, context):
        def status_task():
            return animal_posts_pb2.StatusResponse(status="Service is running", status_code=200)

        return self.run_with_timeout(status_task, 5)

    # get load method implementation
    def GetLoad(self, request, context):
        def load_task():
            with app.app_context():
                total_posts = db.session.query(animal_posts).count()
            return animal_posts_pb2.LoadResponse(load=total_posts, status_code=200)

        return self.run_with_timeout(load_task, 5)

# start the gRPC server
def serve():
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=5))
    animal_posts_pb2_grpc.add_AnimalPostServiceServicer_to_server(AnimalService(), server)
    server.add_insecure_port('[::]:50052')
    print("Animal post server is running")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    register_service("AnimalService", "http://localhost:50052")
    serve()
