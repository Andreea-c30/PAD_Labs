import grpc
import animal_posts_pb2
import animal_posts_pb2_grpc
from models import db, animal_posts
from flask import Flask
import time
import concurrent.futures

app = Flask(__name__)
app.config.from_object('config')
db.init_app(app)

with app.app_context():
    db.create_all()

class AnimalService(animal_posts_pb2_grpc.AnimalPostServiceServicer):
    # run tasks with a timeout
    def run_with_timeout(self, task_func, timeout, *args, **kwargs):
        #creating a thread pool executor for running tasks
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(task_func, *args, **kwargs)
            try:
                # waiting for the task to complete
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print("Request timed out") 
                return animal_posts_pb2.CreateAnimalResponse(postId=0, message="Request timed out after 5 seconds")

    #create a new animal post
    def CreateAnimalPost(self, request, context):
        def create_task():
            new_post = {
                "title": request.title,
                "description": request.description,
                "location": request.location,
                "status": request.status,
                "images": request.images
            }

            with app.app_context():
                # insert the new post into the database
                db.session.execute(animal_posts.insert().values(new_post))
                db.session.commit()  
                #get the ID of the new post
                post_id = db.session.execute(animal_posts.select().order_by(animal_posts.c.id.desc())).fetchone()[0]

            # Return a successful response
            return animal_posts_pb2.CreateAnimalResponse(postId=post_id, message="Post created successfully")
        
        # running the task with a 5sec timeout
        return self.run_with_timeout(create_task, 5)

    #update an existing animal post
    def UpdateAnimalPost(self, request, context):
        def update_task():
            with app.app_context():
                # cheking if the post exists in the database
                post = db.session.execute(animal_posts.select().where(animal_posts.c.id == request.postId)).fetchone()
                if post is None:
                    context.set_details('Post not found')
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return animal_posts_pb2.UpdateAnimalResponse(message="Post not found")
                updated_post = {
                    "title": request.title,
                    "description": request.description,
                    "location": request.location,
                    "status": request.status,
                    "images": request.images
                }
                # update the post
                db.session.execute(animal_posts.update().where(animal_posts.c.id == request.postId).values(updated_post))
                db.session.commit()  

            # return response for post updating
            return animal_posts_pb2.UpdateAnimalResponse(message="Post updated successfully")

        return self.run_with_timeout(update_task, 5)

    #retrieve  animal posts
    def GetAnimals(self, request, context):
        def get_animals_task():
            with app.app_context():
                # fetching posts from the database
                posts = db.session.execute(animal_posts.select()).fetchall()
            animals = []
            for post in posts:
                # converting each post into an AnimalPost message
                animal = animal_posts_pb2.AnimalPost(
                    postId=post.id,
                    title=post.title,
                    description=post.description,
                    location=post.location,
                    status=post.status,
                    images=post.images
                )
                animals.append(animal)

            return animal_posts_pb2.AnimalListResponse(posts=animals)
        return self.run_with_timeout(get_animals_task, 5)

    #delete animal post
    def DeleteAnimalPost(self, request, context):
        def delete_task():
            with app.app_context():
                #checking if the post exists in the database
                post = db.session.execute(animal_posts.select().where(animal_posts.c.id == request.postId)).fetchone()
                if post is None:
                    context.set_details('Post not found')
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return animal_posts_pb2.DeleteAnimalResponse(message="Post not found")

                # delete post from the database
                db.session.execute(animal_posts.delete().where(animal_posts.c.id == request.postId))
                db.session.commit()

            return animal_posts_pb2.DeleteAnimalResponse(message="Post deleted successfully")

        return self.run_with_timeout(delete_task, 5)

    #check the status of the service
    def CheckStatus(self, request, context):
        def status_task():
            return animal_posts_pb2.StatusResponse(status="Service is running")

        return self.run_with_timeout(status_task, 5)

#start the gRPC server
def serve():
    # creating a gRPC server with a thread pool executor for handling requests
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=5))
    # adding the AnimalService to the gRPC server
    animal_posts_pb2_grpc.add_AnimalPostServiceServicer_to_server(AnimalService(), server)
    server.add_insecure_port('[::]:50052')
    print("Animal post server is running") 
    server.start() 
    server.wait_for_termination() 


if __name__ == '__main__':
    serve()
