const express = require('express');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const CircuitBreaker = require('./circuitBreaker');

const router = express.Router();
const ANIMAL_POSTS_PROTO_PATH = './animal_posts.proto';
const circuitBreaker = new CircuitBreaker(3, 3500); // 3 errors in 3.5 seconds to open the circuit

// Load the animal posts service protobuf
const animalPostsPackageDef = protoLoader.loadSync(ANIMAL_POSTS_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true,
});
const animalPostsProto = grpc.loadPackageDefinition(animalPostsPackageDef).animal_posts;

let animalPostsClient;
const cache = {};

// Initialize the gRPC client
const initAnimalPostsClient = (serviceUrl) => {
    animalPostsClient = new animalPostsProto.AnimalPostService(
        serviceUrl,
        grpc.credentials.createInsecure()
    );
};

// Create an animal post
router.post('/', async (req, res) => {
    const { title, description, location, status, images } = req.body;
    const request = { title, description, location, status, images };

    try {
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.CreateAnimalPost(request, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });

        cache['animalPosts'] = null; // Clear cache after creation
        res.status(200).json({ message: response.message, postId: response.postId });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Update an animal post
router.put('/:postId', async (req, res) => {
    const { postId } = req.params;
    const { title, description, location, status, images } = req.body;
    const request = { postId: Number(postId), title, description, location, status, images };

    try {
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.UpdateAnimalPost(request, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });

        cache['animalPosts'] = null; // Clear cache after update
        res.status(200).json({ message: response.message });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Get all animal posts with caching
router.get('/', async (req, res) => {
    if (cache['animalPosts']) {
        return res.status(200).json({ posts: cache['animalPosts'], source: 'cache' });
    }

    try {
        const response = await circuitBreaker.callService(() => {
            return new Promise((resolve, reject) => {
                animalPostsClient.GetAnimals({}, (error, response) => {
                    if (error) return reject(error);
                    resolve(response);
                });
            });
        });

        cache['animalPosts'] = response.posts; // Cache the result
        res.status(200).json({ posts: response.posts, source: response.source || 'database' });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Delete an animal post by ID
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

        cache['animalPosts'] = null; // Clear cache after deletion
        res.status(200).json({ message: response.message });
    } catch (error) {
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Check the status of the Animal Posts service
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
        res.status(500).json({ error: error.details || 'Service unavailable' });
    }
});

// Export the router and initialization function
module.exports = { router, initAnimalPostsClient, animalPostsProto };
