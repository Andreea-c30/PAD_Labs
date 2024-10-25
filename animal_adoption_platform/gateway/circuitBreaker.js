class CircuitBreaker {
    constructor(failureThreshold, timeout) {
        this.failureThreshold = failureThreshold; //nr of failures before service is removed
        this.timeout = timeout;                   //time threshold for failures
        this.failureCount = 0;
        this.state = 'CLOSED';
        this.lastFailureTime = null;
        this.isRemoved = false;
    }

    async callService(serviceCall) {
        if (this.isRemoved) {
            throw new Error('Service has been removed due to repeated failures');
        }

        if (this.state === 'OPEN') {
            const currentTime = Date.now();
            //check if the timeout period has passed to allow HALF-OPEN state
            if (currentTime - this.lastFailureTime > this.timeout) {
                this.state = 'HALF-OPEN'; // Allow a test call
            } else {
                throw new Error('Circuit is open');
            }
        }

        try {
            const result = await serviceCall(); //try calling the service
            this.reset(); //reset state on success
            return result; //return result on success
        } catch (err) {
            this.recordFailure(); //record the failure
            throw err; //propagate the error
        }
    }

    recordFailure() {
        this.failureCount++;
        const currentTime = Date.now();

        if (this.failureCount >= this.failureThreshold && currentTime - this.lastFailureTime <= this.timeout * 3.5) {
            this.removeService(); //remove the service if threshold is met within time limit
        } else if (this.failureCount < this.failureThreshold) {
            this.lastFailureTime = currentTime; //update last failure time if threshold not yet met
        }
    }

    removeService() {
        //mark the service as removed
        this.isRemoved = true;
        console.warn('Service has been removed due to repeated failures');
    }

    reset() {
        this.failureCount = 0;
        if (this.state === 'HALF-OPEN') {
            //move back to CLOSED if HALF-OPEN
            this.state = 'CLOSED';
        }
    }
}

module.exports = CircuitBreaker;
