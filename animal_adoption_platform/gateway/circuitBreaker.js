const axios = require('axios');

class CircuitBreaker {
    constructor(maxFailures, timeout, instances) {
        this.maxFailures = maxFailures; // Maximum allowed failures before tripping the breaker
        this.timeout = timeout; // Timeout for individual service calls
        this.instances = instances; // List of service instances
        this.failures = new Array(instances.length).fill(0); // Failure counters for each instance
        this.currentInstanceIndex = 0; // Index of the current instance
        this.retryWindow = 3.5 * timeout; // Retry delay multiplier
    }

    // Core function to send a request to a service instance
    async callService(serviceCall) {
        while (this.instances.length > 0) {
            const instance = this.instances[this.currentInstanceIndex];
            console.log(`Attempting to send request to instance: ${instance}`);

            try {
                const response = await serviceCall(instance);
                this.resetFailures(this.currentInstanceIndex); // Reset failures for successful instance
                return response; // Return successful response
            } catch (error) {
                this.failures[this.currentInstanceIndex]++;
                console.error(`Failed to send request to ${instance}. Failures: ${this.failures[this.currentInstanceIndex]}`);

                // Remove the instance if failures exceed the threshold
                if (this.failures[this.currentInstanceIndex] >= this.maxFailures) {
                    console.log(`Removing instance ${instance} after ${this.failures[this.currentInstanceIndex]} failures.`);
                    this.instances.splice(this.currentInstanceIndex, 1); // Remove instance
                    this.failures.splice(this.currentInstanceIndex, 1); // Remove corresponding failure count

                    if (this.instances.length === 0) {
                        console.error('All instances have failed.');
                        throw new Error('All instances have failed.');
                    }
                } else {
                    // Ensure we do not go out of bounds after removal
                    if (this.instances.length > 0) {
                        // Move to the next instance in the list
                        this.currentInstanceIndex = this.currentInstanceIndex % this.instances.length;
                    } else {
                        // If no instances remain, reset the index to 0, which will be meaningless but indicate that all failed
                        this.currentInstanceIndex = 0;
                    }
                }
            }
        }

        console.error('Circuit breaker tripped: All retries failed.');
        throw new Error('Circuit breaker tripped: All retries failed.');
    }

    // Resets the failure count for a specific instance
    resetFailures(instanceIndex) {
        this.failures[instanceIndex] = 0;
    }
    onInstanceSwitch(callback) {
        this.instanceSwitchCallback = callback;
    }

    // Update instance switch logic to include callback
    switchToNextInstance() {
        this.currentInstanceIndex = (this.currentInstanceIndex + 1) % this.instances.length;
        if (this.instanceSwitchCallback) {
            this.instanceSwitchCallback(this.instances[this.currentInstanceIndex]);
        }
    }
}

module.exports = CircuitBreaker;
