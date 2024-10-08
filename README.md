# Topic: Animal adoption platform

An animal adoption platform aims to facilitate the adoption process of the helpless animals without shelter by developing an interactive platform. Where volunteers can post lost and homeless animals including detailed information about the animal in need, while potential adopters are able to directly interact with the volunteers who posted the animals.

##	Assess Application Suitability

Distributed systems are a collection of autonomous microsystems that are located separately, but connected by a network. The animal adoption platform is suitable for microservices architecture, because it offers a lot of benefits, including: scalability, fault isolation, faster deployment, and tech agnosticity.

- For a more efficient scalability of the platform, to be able to be extended in several locations and to manage large demands, distributed systems allow the independent scaling of applications according to needs without affecting other components

-  The adoption platform includes 2 services, the publication of homeless animals and the interaction between users through a chat. These 2 services must be separated and developed independently. This fact will increase flexibility and enhance the deployment process, reducing interdependence

- If one of the services goes down, for example the chat that allows interaction between users, the other services related to the posting of information about animals that need help, must remain intact. Thus, by using microservices it is possible to isolate failures without affecting the entire system

- Different services of the application require different technologies, for example for chat it will be necessary to use websockets for communication between client and server in real time, while for posting animals we can use RESTful APIs that do not require real-time interaction and allow a fast and easy way for APIs development.

Similar examples of applications that are using microservices architecture would be Petfinder and Adopt-a-Pet, to manage the listing of available animals, the adoption process, notifications and the message system that allow the scaling and separate management of each individual service without interrupting the overall system

## Service Boundaries

- Animal Posting Service
    1. Creates post about an animal in need
    2. Updates specific post
    3. Deletes a post
    4. Filtering the posts based on location 
- User Interaction Service
    1. Provides a chat for direct communication between potential adopters and volunteers
    2. Storing chat history in non relational database such as MongoDB
    3. Handles notifications for new messages

    ![alt text](https://github.com/Andreea-c30/PAD_Labs/blob/main/img/updated.jpg?raw=true)

## Technology Stack and Communication Patterns

- Animal Posting Service
    - Python as the programing language
    - SQLite as the database
    - gRPC as communication pattern
- User Interaction Service
    - Python as the programing language
    - Redis as the database to store chat history
    - gRPC real time communication pattern
- Gateway 
    - JavaScript as the programming language (Node.js using Express.js)
## Design Data Management

Data management will be carried out in separate databases. SQLite will be used for posts related to animals, and Redis will be used to keep chat history.

Services will communicate with each other using APIs. Also, for data storage it will be used JSON due to its readability and simplicity.

### Animal Posting Service Endpoints: 
 - POST Method:  /animal-posts
    ```
    {
        "title": "string",
        "description": "string",
        "location": "string",
        "status": "available", 
        "images": "string"
    }
    ```
 - Response: 
    ```
    {
        "postId": "string",
        "message": "Post created successfully"
    }
    ```
- PUT Method:  /animal-posts/:postId
    ```
    {
        "title": "string",
        "description": "string",
        "location": "string",
        "status": "available", 
        "images": "string"
    }
    ```
 - Response: 
    ```
    {
        "message": "Post updated successfully"
    }   
    ```
- GET Method:  /animal-posts
 - Response: 
    ```
    {
        "title": "string",
        "description": "string",
        "location": "string",
        "status": "available", 
        "images": "string"
    }
    ```
- DELETE Method: /animal-posts/:postId
- Response: 
    ```
    {
        "message": "Post deleted successfully"
    }   
    ```
### User Interaction Service Endpoints
- POST Method: /chat
    ```
    {
        "username": "string",
        "message": "string",
    }
    ```
- Response: 
    ```
    {
        "response": "Message  received!"
    }
    ```
- GET Method: /chat/history
    ```
    { 
        "messages": [ "username": "message"]
    }
    ```

- GET Method: /chat/history
    ```
    { 
        "messages": [ "username": "message"]
    }
    ```

- GET Method: /chat/status
    ```
    {
    "status": "Server is running"
    }
    ```
- GET Method: /animal-posts/status
    ```
    {
    "status": "Server is running"
    }
    ```
## Set Up Deployment and Scaling

For scaling and deployment of the project it will be used Containerization with Docker. Each microservice and its dependencies will be packaged in a Docker container to ensure consistency in various environments.

The first step is to build Dockerfiles for each individual service. 
Next Docker Images are built using the command:
```
docker build [OPTIONS] PATH | URL
```

Then run the Docker image:
```
docker run -p 8080:80 sampleapp:v1
```
And lastly with the container running,we can access the application