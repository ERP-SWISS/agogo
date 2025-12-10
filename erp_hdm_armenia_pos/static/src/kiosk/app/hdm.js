import { rpc } from "@web/core/network/rpc";

const REQUEST_TIMEOUT = 3000;

export class HdmError extends Error {}

export class Hdm {
    constructor(...args) {
        this.setup(...args);
    }

    setup(env, hdmPaymentMethod, access_token, pos_config, errorCallback) {
        this.env = env;
        this.access_token = access_token;
        this.hdmPaymentMethod = hdmPaymentMethod;
        this.pos_config = pos_config;
        this.errorCallback = errorCallback;
        this.savedOrder = false;
        this.pollTimeout = null;
        this.payment_stopped = false;
    }

    async handleHdmResponse(response){
        if (response?.error) {
            this.payment_stopped
                ? this.errorCallback(new HdmError("Transaction canceled due to inactivity"))
                : this.errorCallback(new HdmError(response.error));
            return false;
        }
        return true;
    }

    async startPayment(order) {
         await this.processPayment(order);
    }
    async processPayment(order) {
        try {
            const initial_response = await rpc(`/kiosk/payment/${this.pos_config.id}/kiosk`, {
                order: order.serializeForORM(),
                access_token: this.access_token,
                payment_method_id: this.hdmPaymentMethod.id,
            });
            if (initial_response) {
                this.savedOrder = initial_response.order[0];
                return this.handleHdmResponse(initial_response.payment_status);
            }
        } catch (error) {
            console.log('HDM processPayment error', error)
            this.errorCallback(error);
            return false;
        }
    }
}
