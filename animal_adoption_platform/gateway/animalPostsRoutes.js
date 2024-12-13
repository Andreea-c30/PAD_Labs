// animalPostsRoutes.js
const express = require('express');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const CircuitBreaker = require('./circuitBreaker');
const redis = require('redis');

const router = express.Router();
const ANIMAL_POSTS_PROTO_PATH = './animal_posts.proto';

// Initialize Redis Client
const redisClient = redis.createClient({
    socket: {
        host: 'redis',
        port: 6379,
    },
});

// Redis Error Handling
redisClient.on('error', (err) => console.error('Redis Client Error:', err));

// Connect to Redis
(async () => {
    try {
        await redisClient.connect();
        console.log('Connected to Redis');
    } catch (err) {
        console.error('Could not connect to Redis:', err.message);
    }
})();

// Service Instances
const instances = [
    'http://animal-post-service-1:50052',
    'http://animal-post-service-2:50052',
    'http://animal-post-service-3:50052',
];

// Circuit Breaker Setup
const circuitBreaker = new CircuitBreaker(3, 3500, instances); // 3 errors before switching instances

// Load gRPC Service
const animalPostsPackageDef = protoLoader.loadSync(ANIMAL_POSTS_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true,
});
const animalPostsProto = grpc.loadPackageDefinition(animalPostsPackageDef).animal_posts;
let animalPostsClient;

// Initialize gRPC Client
const initAnimalPostsClient = (serviceUrl) => {
    animalPostsClient = new animalPostsProto.AnimalPostService(
        serviceUrl,
        grpc.credentials.createInsecure()
    );
};

// Helper to Clear Redis Cache
const clearRedisCache = async (key) => {
    try {
        await redisClient.del(key);
        console.log(`Cache cleared for key: ${key}`);
    } catch (err) {
        console.error(`Failed to clear Redis cache for key ${key}:`, err.message);
    }
};

// Create Animal Post
router.post('/', async (req, res) => {
    const { title, description, location, status } = req.body;
    const request = { title, description, location, status };

    try {
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.CreateAnimalPost(request, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });

        // Clear Cache After Creating a Post
        await clearRedisCache('animalPosts');

        res.status(200).json({ message: response.message, postId: response.postId });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Update Animal Post
router.put('/:postId', async (req, res) => {
    const { postId } = req.params;
    const { title, description, location, status } = req.body;
    const request = { postId: Number(postId), title, description, location, status };

    try {
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.UpdateAnimalPost(request, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });

        // Clear Cache After Updating a Post
        await clearRedisCache('animalPosts');

        res.status(200).json({ message: response.message });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Fetch All Animal Posts with Cache
router.get('/', async (req, res) => {
    try {
        // Check Cache
        const cachedPosts = await redisClient.get('animalPosts');
        if (cachedPosts) {
            console.log('Cache hit');
            return res.status(200).json({ posts: JSON.parse(cachedPosts), source: 'cache' });
        }

        // Fetch from gRPC Service if Cache Miss
        console.log('Cache miss, calling gRPC service');
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.GetAnimals({}, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });

        // Cache Response
        await redisClient.set('animalPosts', JSON.stringify(response.posts), {
            EX: 300, // Expire after 300 seconds (5 minutes)
        });

        res.status(200).json({ posts: response.posts, source: 'database' });
    } catch (error) {
        console.error('Error in GetAnimals route:', error.message);
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Delete Animal Post
router.delete('/:postId', async (req, res) => {
    const { postId } = req.params;
    const request = { postId: Number(postId) };

    try {
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.DeleteAnimalPost(request, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });

        // Clear Cache After Deleting a Post
        await clearRedisCache('animalPosts');

        res.status(200).json({ message: response.message });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});
// Endpoint pentru testarea circuit breaker-ului și a instanțelor serviciului
router.get('/test_failover', async (req, res) => {
    try {
        // Încercăm să obținem postările
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                // Simulăm o eroare 500 pentru a testa failover-ul
                // Aici se simulează o eroare în momentul în care gateway-ul face cererea către serviciul gRPC
                const simulateError = 1 + Math.random() > 0.5; // Probabilitate de 50% pentru a simula eroare
                if (simulateError) {
                    reject(new Error('Simulăm eroare 500 la serviciu'));
                } else {
                    // Dacă nu există eroare, continuăm cu răspunsul normal
                    animalPostsClient.GetAnimals({}, (error, response) => {
                        if (error) return reject(error);
                        resolve(response);
                    });
                }
            });
        });
        res.status(200).json({ message: 'success', posts: response.posts });
    } catch (error) {
        // În cazul unei erori, returnăm un mesaj de tip 500
        res.status(500).json({ error: 'Instance failed', message: error.message });
    }
});


// Verificarea stării serviciului AnimalPosts
router.get('/status', async (req, res) => {
    try {
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.CheckStatus({}, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });
        res.status(200).json({ status: response.status });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Serviciu indisponibil' });
    }
});

module.exports = { router, initAnimalPostsClient };
