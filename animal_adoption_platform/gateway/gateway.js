//gateway.js
const express = require('express');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const WebSocket = require('ws');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');
const connectPrometheus = require('./prometheus');
const CircuitBreaker = require('./circuitBreaker');


// Import routes and gRPC client initialization
const { router: animalPostsRoutes, initAnimalPostsClient } = require('./animalPostsRoutes');
const ANIMAL_POST_SERVICE_URL = 'http://animal_posts_service:50052';

// Configuration
const CHAT_WS_URL = 'ws://new_chat:6789';
const CHAT_API_URL = 'http://new_chat:9100';
const CRITICAL_LOAD_THRESHOLD = 60;
const FAILURE_THRESHOLD = 3;
const TIMEOUT = 5000;
// Load gRPC definitions
const ANIMAL_POSTS_PROTO_PATH = './animal_posts.proto';
const packageDefinition = protoLoader.loadSync(ANIMAL_POSTS_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true,
});
const animalPostsProto = grpc.loadPackageDefinition(packageDefinition).animal_posts;
const animalPostsClient = new animalPostsProto.AnimalPostService(
    'animal_posts_service:50052',
    grpc.credentials.createInsecure()
);

// Initialize Express app
const app = express();
app.use(express.json());
app.use('/animal-posts', animalPostsRoutes);


connectPrometheus(app); 

// Instanțele serviciului AnimalPost
const animalPostInstances = [
    'http://animal-post-service-1:50052',
    'http://animal-post-service-2:50052',
    'http://animal-post-service-3:50052'
];

// Initialize Circuit Breaker pentru serviciul AnimalService
const circuitBreakerAnimalService = new CircuitBreaker(FAILURE_THRESHOLD, TIMEOUT, animalPostInstances);

// Alerts for critical load conditions
const alertCriticalLoad = (load, serviceName) => {
    if (load > CRITICAL_LOAD_THRESHOLD) {
        console.warn(`ALERT: ${serviceName} is under critical load: ${load} requests per second.`);
    }
};

// Retry service calls if they fail
const retryServiceCall = async (circuitBreaker, serviceCall, serviceName) => {
    try {
        // Apelăm serviciul folosind circuit breaker
        return await circuitBreaker.callService(serviceCall);
    } catch (error) {
        console.error(`RetryServiceCall: All retries failed for ${serviceName}.`, error.message);
        throw error; // Retrimitem eroarea pentru a gestiona eventual în endpoint
    }
};


// Descoperirea serviciului URL cu protecție din circuit breaker
const discoverService = async (serviceName) => {
    try {
        return await retryServiceCall(circuitBreakerAnimalService, async () => {
            const response = await axios.get(`http://service_discovery:3001/services/${serviceName}`);
            return response.data.url.replace(/^http:\/\//, ''); // Returnează doar URL-ul fără "http://"
        }, serviceName);
    } catch (error) {
        console.error(`Circuit Breaker Alert for ${serviceName}:`, error.message);
        throw error;
    }
};

// Initialize WebSocket connection to the chat service
let wsChatClient;
const createWsChatClient = () => {
    const wsClient = new WebSocket(CHAT_WS_URL);

    wsClient.on('open', () => {
        console.log('WebSocket connected');
    });

    wsClient.on('message', (data) => {
        try {
            const messageData = JSON.parse(data);

            if (messageData.action === 'message_saved') {
                console.log(`Message saved confirmation: ${JSON.stringify(messageData)}`);
                // Handle message saved confirmation
            } else if (messageData.system) {
                console.log(`System message received: ${messageData.system}`);
                // Optionally broadcast to other clients or handle as needed
            } else {
                console.warn(`Unexpected WebSocket message: ${JSON.stringify(messageData)}`);
            }
        } catch (err) {
            console.error('Error parsing WebSocket message:', err.message);
        }
    });

    wsClient.on('error', (error) => {
        console.error(`WebSocket error: ${error.message}`);
    });

    wsClient.on('close', () => {
        console.log('WebSocket connection closed, attempting to reconnect...');
        reconnectWebSocket();
    });

    wsChatClient = wsClient; // Assign to the global variable
    return wsClient;
};


// Function to handle WebSocket reconnection
const reconnectWebSocket = () => {
    setTimeout(() => {
        console.log('Reinitializing WebSocket connection...');
        wsChatClient = createWsChatClient(); // Reinitialize WebSocket client
    }, 10000); // Retry connecting after 5 seconds
};

// Initialize WebSocket client
wsChatClient = createWsChatClient();


// Initialize chat rooms and WebSocket clients
const chatRooms = {}; // Store chat rooms and their participants
// In-memory storage for users and their WebSocket connections
const userSockets = {}; // Maps username to their WebSocket client

// Endpoint to join a chat room
app.post('/chat/join', (req, res) => {
    const { username } = req.body;

    // Create a new WebSocket for each user if they don't have one already
    if (!userSockets[username]) {
        const userSocket = createWsChatClient();

        userSocket.on('open', () => {
            const room = req.body.room || 'lobby'; // Default to lobby if no room is specified
            if (!chatRooms[room]) {
                chatRooms[room] = { clients: [] }; // Create room if it doesn't exist
            }
            chatRooms[room].clients.push(userSocket); // Add client to the room
            userSockets[username] = userSocket; // Store WebSocket for this user
            res.status(200).json({ message: `User ${username} joined room ${room}` });
        });

        userSocket.on('error', (error) => {
            console.error(`WebSocket error for ${username}: ${error.message}`);
        });
    } else {
        res.status(400).json({ error: `User ${username} is already connected` });
    }
});
// Proxy the chat server health check
app.get('/chat/health', async (req, res) => {
    try {
        const response = await axios.get(`${CHAT_API_URL}/health`);
        res.status(response.status).json(response.data);
    } catch (error) {
        console.error('Error connecting to chat server /health endpoint:', error.message);
        res.status(500).json({ error: 'Failed to connect to chat server' });
    }
});

// Endpoint to send a chat message to a specific room

app.post('/chat/message', async (req, res) => {
    const { username, room, message } = req.body;

    if (!username || !message) {
        return res.status(400).json({ error: "Missing 'username' or 'message'" });
    }

    try {
        console.log('Forwarding message to Flask:', { username, room, message });
        const response = await axios.post(`${CHAT_API_URL}/add_message`, { username, room, message });
        console.log('Response from Flask:', response.data);
        res.status(response.status).json(response.data);
    } catch (error) {
        console.error('Error from Flask:', error.response?.data || error.message);
        res.status(500).json({ error: 'Failed to save message' });
    }
});


// // Endpoint to send a chat message to a specific room
// app.post('/chat/adopt', (req, res) => {
//     const { username, room, message, animal_id } = req.body;

//     // Retrieve the stored WebSocket connection for the user
//     const userSocket = userSockets[username];

//     if (userSocket && userSocket.readyState === WebSocket.OPEN) {
//         const chatData = JSON.stringify({ username, room, animal_id, action: 'adopt' });
        
//         // Send the message via the user's WebSocket connection
//         userSocket.send(chatData, (err) => {
//             if (err) {
//                 console.error(`Failed to send message for ${username}: ${err.message}`);
//                 return res.status(500).json({ error: 'Failed to send message' });
//             }
//             res.status(200).json({ message: 'Adoption sent to chat room' });
//         });
//     } else {
//         console.error(`WebSocket for ${username} is not open or doesn't exist`);
//         res.status(500).json({ error: 'WebSocket connection is not open' });
//     }
// });

// Endpoint to check the WebSocket connection status
app.get('/chat/status', (req, res) => {
    if (!wsChatClient) {
        return res.status(500).json({ status: 'WebSocket client is not initialized' });
    }

    const wsStatus = wsChatClient.readyState;

    let statusMessage = '';
    switch (wsStatus) {
        case WebSocket.CONNECTING:
            statusMessage = 'WebSocket is connecting...';
            break;
        case WebSocket.OPEN:
            statusMessage = 'WebSocket is open and connected';
            break;
        case WebSocket.CLOSING:
            statusMessage = 'WebSocket is closing...';
            break;
        case WebSocket.CLOSED:
            statusMessage = 'WebSocket is closed or failed to open';
            break;
        default:
            statusMessage = 'Unknown WebSocket status';
    }

    res.status(200).json({ status: statusMessage });
});

// Status endpoint for the gateway
app.get('/status', (req, res) => {
    res.status(200).json({ status: 'Gateway is running', timestamp: new Date() });
});
/////////////////////////testing routes
app.post('/db/test-insert', async (req, res) => {
    try {
        const response = await axios.post(`${CHAT_API_URL}/add_test_message`);
        res.status(response.status).json(response.data);
    } catch (error) {
        console.error('Error inserting test message:', error.message);
        res.status(500).json({ error: 'Failed to insert test message' });
    }
});
app.get('/db/get-messages/:room', async (req, res) => {
    const { room } = req.params;
    try {
        const response = await axios.get(`${CHAT_API_URL}/get_messages/${room}`);
        res.status(response.status).json(response.data);
    } catch (error) {
        console.error('Error retrieving messages:', error.message);
        res.status(500).json({ error: 'Failed to retrieve messages' });
    }
});

app.post('/chat/adopt', async (req, res) => {
    const { username, room, message,animal_id } = req.body;

    if (!username || !room ||!message|| !animal_id) {
        return res.status(400).json({ error: "Missing 'username', 'room', or 'animal_id'" });
    }

    const transactionId = uuidv4();

    try {
        // Prepare Phase
        console.log('Starting prepare phase for transaction:', transactionId);

        // Prepare with animal posts service
        const animalPrepare = await new Promise((resolve, reject) => {
            animalPostsClient.Prepare(
                {
                    transaction_id: transactionId,
                    payload: JSON.stringify({ postId: animal_id }),
                    operation: 'adopt',
                },
                (error, response) => {
                    if (error || !response.success) {
                        return reject(error || new Error(response.message));
                    }
                    resolve(response);
                }
            );
        });

        console.log('AnimalPostService prepare successful:', animalPrepare);

        // Prepare with chat service
        const chatPrepare = await axios.post(`${CHAT_API_URL}/prepare`, {
            transaction_id: transactionId,
            username,
            room,
            action: 'adopt',
            message,
            animal_id,
        });

        if (chatPrepare.data.status !== 'ready') {
            throw new Error('Chat service prepare failed');
        }

        console.log('ChatService prepare successful:', chatPrepare.data);

        // Commit Phase
        console.log('Starting commit phase for transaction:', transactionId);

        // Commit with animal posts service
        const animalCommit = await new Promise((resolve, reject) => {
            animalPostsClient.Commit(
                {
                    transaction_id: transactionId,
                    operation: 'adopt',
                },
                (error, response) => {
                    if (error || !response.success) {
                        return reject(error || new Error(response.message));
                    }
                    resolve(response);
                }
            );
        });

        console.log('AnimalPostService commit successful:', animalCommit);

        // Commit with chat service
        const chatCommit = await axios.post(`${CHAT_API_URL}/commit`, {
            transaction_id: transactionId,
            username,
            room,
            message,
            animal_id,
        });

        if (chatCommit.data.status !== 'committed') {
            throw new Error('Chat service commit failed');
        }

        console.log('ChatService commit successful:', chatCommit.data);

        // Transaction completed successfully
        return res.status(200).json({ message: 'Adoption transaction completed successfully' });
    } catch (error) {
        console.error('Transaction failed, starting rollback phase for transaction:', transactionId);

        // Rollback Phase
        const rollbackErrors = [];

        // Rollback animal posts service
        try {
            // Retry rollback for AnimalPostService
            await new Promise((resolve, reject) => {
                animalPostsClient.Rollback(
                    { transaction_id: transactionId },
                    (error, response) => {
                        if (error || !response.success) {
                            return reject(error || new Error(response.message));
                        }
                        resolve(response);
                    }
                );
            });
        } catch (animalRollbackError) {
            console.error('Retry failed for AnimalPostService rollback:', animalRollbackError.message);
        }
        

        // Rollback chat service
        try {
            await axios.post(`${CHAT_API_URL}/rollback`, {
                transaction_id: transactionId,
                username,
                room,
                message,
                animal_id,
            });
            console.log('ChatService rollback successful for transaction:', transactionId);
        } catch (chatRollbackError) {
            console.error('Failed to rollback ChatService:', chatRollbackError.message);
            rollbackErrors.push('ChatService rollback failed');
        }

        if (rollbackErrors.length > 0) {
            console.error('Rollback encountered issues:', rollbackErrors);
        }

        return res.status(500).json({
            error: 'Transaction failed and rolled back',
            details: error.message,
            rollback_errors: rollbackErrors,
        });
    }
});


// Start the gateway server
const startServer = async () => {
    try {
        const ANIMAL_SERVICE_URL = await discoverService('AnimalService');
        initAnimalPostsClient(ANIMAL_SERVICE_URL);
        app.use('/animal-posts', animalPostsRoutes);

        // Start the gateway server
        const PORT = 3000;
        app.listen(PORT, () => {
            console.log(`Gateway server is running on port ${PORT}`);
        });
    } catch (error) {
        console.error('Error starting the server:', error.message);
    }
};

// Start the server
startServer();
