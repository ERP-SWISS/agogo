import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { Hdm, HdmError } from "@erp_hdm_armenia_pos/kiosk/app/hdm";

patch(SelfOrder.prototype, {
    async setup() {
        await super.setup(...arguments);

        const hdmPaymentMethod = this.models["pos.payment.method"].find(
            (p) => p.use_payment_terminal === "hdm"
        );

        if (hdmPaymentMethod) {
            this.hdm = new Hdm(
                this.env,
                hdmPaymentMethod,
                this.access_token,
                this.config,
                this.handleHdmError.bind(this)
            );
        }
    },
    handleHdmError(error, type) {
        this.paymentError = true;
        this.handleErrorNotification(error, type);
    },

    handleErrorNotification(error, type = "danger") {
        let errorMessage = "";
        if (error instanceof HdmError) {
            errorMessage = `Hdm POS: ${error.message}`;
            this.notification.add(errorMessage, {
                type: type,
            });
        } else {
            super.handleErrorNotification(...arguments);
        }
    },
    filterPaymentMethods(paymentMethods) {
        let methods = super.filterPaymentMethods(...arguments);
        if (this.hdm) {
            methods.push(this.hdm.paymentMethod);
        }
        return methods;
    }
});
