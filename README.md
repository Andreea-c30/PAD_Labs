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

- User authentification
    1. User sign up
    2. User log in 
- Animal Posting Service
    1. Creates post about an animal in need
    2. Updates specific post
    3. Deletes a post
    4. Filtering the posts based on location 
- User Interaction Service
    1. Provides a chat for direct communication between potential adopters and volunteers
    2. Storing chat history in non relational database such as MongoDB
    3. Handles notifications for new messages

![alt text](https://github.com/[username]/[reponame]/blob/[branch]/image.jpg?raw=true)

## Technology Stack and Communication Patterns

- Animal Posting and User authentification Service
    - Python as the programing language
    - PostgreSQL as the database
    - RESTful API as communication pattern
- User Interaction Service
    - Python as the programing language
    - MongoDB as the database
    - WebSocket for real time communication pattern
- Gateway 
    - JavaScript as the programming language (Node.js using Express.js)
## Design Data Management

Data management will be carried out in separate databases. PostgreSQL will be used for posts related to animals, and MongoBD will be used to keep chat history.

Services will communicate with each other using APIs. Also, for data storage it will be used JSON due to its readability and simplicity.
### User Authentication Service Endpoints: 
- POST Method:  /api/auth/signup
    ```
    {
        "username": "string",
        "email": "string",
        "password": "string"
    }

    ```
 - Response: 
    ```
    {
        "userId": "string",
        "message": "User created successfully"
    }
    ```

    - POST Method:  /api/auth/login
    ```
    {
        "username": "string",
        "password": "string"
    }

    ```
 - Response: 
    ```
    {
        "userId": "string",
        "message": "Login successful"
    }
    ```
### Animal Posting Service Endpoints: 
 - POST Method:  /api/animals
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
- PUT Method:  /api/animals/:postId
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
- GET Method:  /api/animals
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
- DELETE Method: /api/animals/:postId
- Response: 
    ```
    {
        "message": "Post deleted successfully"
    }   
    ```
### User Interaction Service Endpoints
- POST Method: /api/chat/messages
    ```
    {
        "senderId": "string",
        "receiverId": "string",
        "message": "string",
        "timestamp": "string"
    }
    ```
- Response: 
    ```
    {
        "messageId": "string",
        "message": "Message sent successfully"
    }

    ```
- GET Method: /api/chat/history
    ```
    {
        "senderId": "string",
        "receiverId": "string",
        "message": "string",
        "timestamp": "string"
    }
    ```
- Response: 
    ```
    {
        "messageId": "string",
        "message": "Message sent successfully"
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
