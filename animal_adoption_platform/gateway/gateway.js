const express = require('express');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const WebSocket = require('ws');
const axios = require('axios');
const CircuitBreaker = require('./circuitBreaker');

const { router: animalPostsRoutes, initAnimalPostsClient, animalPostsProto } = require('./animalPostsRoutes');

const CHAT_WS_URL = 'ws://localhost:6789';
const ANIMAL_POSTS_PROTO_PATH = './animal_posts.proto';
const CRITICAL_LOAD_THRESHOLD = 6;
const FAILURE_THRESHOLD = 3;
const TIMEOUT = 5000;

const app = express();
app.use(express.json());

//initialize Circuit Breakers for each service
const circuitBreakerAnimalService = new CircuitBreaker(FAILURE_THRESHOLD, TIMEOUT);
const circuitBreakerChatService = new CircuitBreaker(FAILURE_THRESHOLD, TIMEOUT);

const alertCriticalLoad = (load, serviceName) => {
    if (load > CRITICAL_LOAD_THRESHOLD) {
        console.warn(`ALERTING SYSTEM: ${serviceName} is under critical load: ${load} pings per second.`);
    }
};

const discoverService = async (serviceName) => {
    try {
        return await circuitBreakerAnimalService.callService(async () => {
            const response = await axios.get(`http://localhost:3001/services/${serviceName}`);
            return response.data.url.replace(/^http:\/\//, '');
        });
    } catch (error) {
        console.error(`Circuit Breaker Alert for ${serviceName}:`, error.message);
        throw error;
    }
};

const updateServiceLoad = async (serviceName, serviceUrl, load) => {
    try {
        await circuitBreakerAnimalService.callService(async () => {
            await axios.post('http://localhost:3001/services/load', {
                serviceName,
                serviceUrl,
                load,
            });
        });
    } catch (error) {
        console.error(`Error updating load for ${serviceName} at ${serviceUrl}:`, error.message);
    }
};

//async function to initialize the gateway
const startServer = async () => {
    try {
        const ANIMAL_SERVICE_URL = await discoverService('AnimalService');
        initAnimalPostsClient(ANIMAL_SERVICE_URL);
        app.use('/animal-posts', animalPostsRoutes);

        const wsChatClient = new WebSocket(CHAT_WS_URL);
        const chatHistory = [];

        setInterval(async () => {
            try {
                const load = await getLoadFromGrpcClient(ANIMAL_SERVICE_URL, animalPostsProto);
                await updateServiceLoad('AnimalService', ANIMAL_SERVICE_URL, load);
                alertCriticalLoad(load, 'AnimalService');
            } catch (error) {
                console.error('Error in service load check:', error.message);
            }
        }, 5000);

        const getLoadFromGrpcClient = async (serviceUrl, proto) => {
            return await circuitBreakerAnimalService.callService(() => {
                return new Promise((resolve, reject) => {
                    const client = new proto.AnimalPostService(
                        serviceUrl,
                        grpc.credentials.createInsecure()
                    );
                    client.GetLoad({}, (err, response) => {
                        if (err) return reject(err);
                        resolve(response.load);
                    });
                });
            });
        };

        //chat routes
        app.post('/chat', async (req, res) => {
            const { username, message } = req.body;
            try {
                await circuitBreakerChatService.callService(() => {
                    return new Promise((resolve, reject) => {
                        if (wsChatClient.readyState === WebSocket.OPEN) {
                            const chatData = JSON.stringify({ username, message });
                            wsChatClient.send(chatData, (err) => {
                                if (err) return reject(new Error('Failed to send message'));
                                resolve();
                            });
                        } else {
                            reject(new Error('WebSocket connection is not open'));
                        }
                    });
                });
                res.status(200).json({ message: 'Message sent to chat server' });
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        });

        app.get('/chat/history', (req, res) => {
            if (wsChatClient.readyState === WebSocket.OPEN) {
                const requestData = JSON.stringify({ action: 'get_history' });
                wsChatClient.send(requestData, (err) => {
                    if (err) {
                        return res.status(500).json({ error: 'Failed to request chat history' });
                    }
                    setTimeout(() => {
                        res.status(200).json({ messages: chatHistory });
                    }, 100); // Delay for history to be populated
                });
            } else {
                res.status(500).json({ error: 'WebSocket connection is not open' });
            }
        });

        app.get('/chat/status', (req, res) => {
            let wsStatus = '';
            switch (wsChatClient.readyState) {
                case WebSocket.CONNECTING:
                    wsStatus = 'Connecting';
                    break;
                case WebSocket.OPEN:
                    wsStatus = 'Open';
                    break;
                case WebSocket.CLOSING:
                    wsStatus = 'Closing';
                    break;
                case WebSocket.CLOSED:
                    wsStatus = 'Closed';
                    break;
                default:
                    wsStatus = 'Unknown';
            }
            res.status(200).json({ websocket_status: wsStatus });
        });

        //status endpoint for the gateway
        app.get('/status', (req, res) => {
            res.status(200).json({ status: 'Gateway is running', timestamp: new Date() });
        });

        //start the server
        const PORT = 3000;
        app.listen(PORT, () => {
            console.log(`Gateway server is running on port ${PORT}`);
        });
    } catch (error) {
        console.error('Error starting the server:', error.message);
    }
};

startServer();
