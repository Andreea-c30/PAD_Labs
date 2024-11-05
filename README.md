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
- User Interaction Service
    1. Provides a chat for direct communication between potential adopters and volunteers
    2. Storing chat history in non relational database such as MongoDB
    3. Handles notifications for new messages

    ![alt text](https://github.com/Andreea-c30/PAD_Labs/blob/main/img/arhitectura_updated.jpg)

## Technology Stack and Communication Patterns

- Animal Posting Service
    - Python as the programing language
    - SQLite as the database
    - gRPC as communication pattern
    - Circuit Breaker to handle API failures gracefully
- User Interaction Service
    - Python as the programing language
    - MongoDB as the database to store chat history
    - Websokets real time communication pattern
    - Circuit Breaker to prevent chat service disruptions from affecting other services
- Gateway 
    - JavaScript as the programming language (Node.js using Express.js)
      
    - Monitoring and Logging integrating ELK for log aggregation
- Cache service
     - Redis for consistent hashing and caching
     - High availability - Redis cluster setup with replica nodes for fault tolerance
      
- Monitoring Stack
    - ELK Stack to aggregate logs from all services
      
- ETL Service & Data Warehouse:
    - Periodically extracts data from SQLite and Redis to a data warehouse for reporting and analytics purposes
## Design Data Management

Data management will be carried out in separate databases. SQLite will be used for posts related to animals, and MongoDb will be used to keep chat history.

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
- POST Method: /chat/join
    ```
    {
        "username": "string",
        "action":  "string",
        "room":  "string"
    }
    ```
- Response: 
    ```
    {
        "response": "User joined the room"
    }
    ```
- POST Method: /chat/message
    ```
    {
        "username": "string",
        "room":  "string",
        "message":  "string",
    }
    ```
- Response: 
    ```
    {
        "response": "User sent message to the room"
    }
    ```

- GET Method: /chat/history/:roomId
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
2 Phase Commits
The endpoint to handle a transaction that creates data in both services, such as when a new adoption request is created, which involves adding records in both the Animal posts service's database and the Chat History database.
Phase 1: Prepare Phase
- POST Method: /adoption-request - initiates a 2PC transaction to add an adoption request across Animal Posts Service and Chat Service
  ```
  {
  "userId": "string",
  "animalId": "string",
  "adoptionMessage": "string"
  }
 
  ```
- POST Method: /prepare-adoption - initiates a 2PC transaction to add an adoption request across Animal Posts Service and Chat Service
  ```
  {
  "transactionId": "transactionId",
  "userId": "string",
  "animalId": "string",
  "adoptionMessage": "string"
  }
  ```
Response :
```
{
  "transactionId": "transactionId",
  "status": "prepared"/"failed"
}
```

Phase 2: Commit or Abort Phase

- POST Method: /commit-adoption - write the data to its database

```
{
  "transactionId": "transactionId"
}

```

- POST Method: /abort-adoption - rollback if any changes were made

```
{
  "transactionId": "transactionId"
}
```

If all services return prepared, the transaction can proceed to the commit phase. If any service returns failed, the transaction will be aborted.

## Set Up Deployment and Scaling

For scaling and deployment of the project it will be used Containerization with Docker. Each microservice and its dependencies will be packaged in a Docker container to ensure consistency in various environments.

The first step is to build Dockerfiles for each individual service. 

Then to launch all services with one command it was created a docker-compose.yml:
```
version: '3.8'

services:
  animal_posts_service:
    build:
      context: ./animal_posts_service
    ports:
      - "50052:50052"
    environment:
      - DATABASE_URL=sqlite:///animal_posts.db
    volumes:
      - animal_posts_data:/app/animal_posts.db

  new_chat:
    build:
      context: ./new_chat
    ports:
      - "6789:6789"
    depends_on:
      - service_discovery
      - mongo

  gateway:
    build:
      context: ./gateway
    ports:
      - "3000:3000"
    environment:
      - SERVICE_DISCOVERY_URL=http://service_discovery:3001
      - CHAT_SERVICE_URL=ws://new_chat:6789
    depends_on:
      - service_discovery
      - animal_posts_service
      - new_chat

  service_discovery:
    build:
      context: ./service_discovery
    ports:
      - "3001:3001"

  mongo:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  animal_posts_data:
  mongo_data:

```
And it is build using the command:
```
docker-compose up --build
```
And lastly with the container running ,we can access the application using Postman
