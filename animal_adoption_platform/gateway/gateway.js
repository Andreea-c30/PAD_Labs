const express = require('express');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

//loading protobuf files
const CHAT_PROTO_PATH = './chat.proto';
const ANIMAL_POSTS_PROTO_PATH = './animal_posts.proto';

// loading chat service protobuf
const chatPackageDef = protoLoader.loadSync(CHAT_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});
const chatProto = grpc.loadPackageDefinition(chatPackageDef).chat;

// loading animal posts service protobuf
const animalPostsPackageDef = protoLoader.loadSync(ANIMAL_POSTS_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});
const animalPostsProto = grpc.loadPackageDefinition(animalPostsPackageDef).animal_posts;

// creating gRPC clients for both services
const chatClient = new chatProto.Chat('localhost:50051', grpc.credentials.createInsecure());
const animalPostsClient = new animalPostsProto.AnimalPostService('localhost:50052', grpc.credentials.createInsecure());

const app = express();
app.use(express.json()); 



// routes of the chat service

// Sending a message
app.post('/chat', (req, res) => {
    const { username, message } = req.body;
    const call = chatClient.ChatStream();
    call.on('data', (response) => {
        res.status(200).json({ response: response.response });
    });

    call.on('error', (error) => {
        res.status(500).json({ error: error.details });
    });

    call.write({ username, message });
    call.end();
});

// get  chat server status
app.get('/chat/status', (req, res) => {
    chatClient.GetStatus({}, (error, response) => {
        if (error) {
            return res.status(500).json({ error: error.details });
        }
        res.status(200).json({ status: response.status });
    });
});

// Get chat history
app.get('/chat/history', (req, res) => {
    chatClient.GetChatHistory({}, (error, response) => {
        if (error) {
            return res.status(500).json({ error: error.details });
        }
        res.status(200).json({ messages: response.messages });
    });
});


//Animal posts routes 
const cache = {}; 

// Creating an animal post
app.post('/animal-posts', (req, res) => {
    const { title, description, location, status, images } = req.body;

    const request = {
        title,
        description,
        location,
        status,
        images
    };

    animalPostsClient.CreateAnimalPost(request, (error, response) => {
        if (error) {
            return res.status(500).json({ error: error.details });
        }
        // clearing the cache when a new post is created
        cache['animalPosts'] = null;
        res.status(200).json({ message: response.message, postId: response.postId });
    });
});

// update an animal post
app.put('/animal-posts/:postId', (req, res) => {
    const { postId } = req.params;
    const { title, description, location, status, images } = req.body;

    const request = {
        postId: Number(postId),
        title,
        description,
        location,
        status,
        images
    };

    animalPostsClient.UpdateAnimalPost(request, (error, response) => {
        if (error) {
            return res.status(500).json({ error: error.details });
        }
        // clearing the cache when a post is updated
        cache['animalPosts'] = null; 
        res.status(200).json({ message: response.message });
    });
});

// Get method animal posts
app.get('/animal-posts', (req, res) => {
    // checking if data exists in the cache
    if (cache['animalPosts']) {
        //return data from cache
        return res.status(200).json({ 
            posts: cache['animalPosts'], 
            source: 'cache' 
        });
    }

    //gRPC call to get the animal posts from db
    animalPostsClient.GetAnimals({}, (error, response) => {
        if (error) {
            return res.status(500).json({ error: error.details });
        }
        //store data in cache for future use
        cache['animalPosts'] = response.posts;
        res.status(200).json({ 
            posts: response.posts, 
            source: response.source || 'database' 
        });
    });
});

// delete an animal post by id
app.delete('/animal-posts/:postId', (req, res) => {
    const { postId } = req.params;

    const request = {
        postId: Number(postId)
    };

    animalPostsClient.DeleteAnimalPost(request, (error, response) => {
        if (error) {
            return res.status(500).json({ error: error.details });
        }
        // clearing cache when a post is deleted
        cache['animalPosts'] = null; 
        res.status(200).json({ message: response.message });
    });
});

// check the status of the Animal Posts service
app.get('/animal-posts/status', (req, res) => {
    animalPostsClient.CheckStatus({}, (error, response) => {
        if (error) {
            return res.status(500).json({ error: error.details });
        }
        res.status(200).json({ status: response.status });
    });
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Gateway server is running on port ${PORT}`);
});
