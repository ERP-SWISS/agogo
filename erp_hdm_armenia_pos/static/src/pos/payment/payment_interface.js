import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class HdmPaymentArmeniaPos extends PaymentInterface {
    setup() {
        super.setup(...arguments);
    }
    get fastPayments() {
        return false
    }
    sendPaymentRequest(uuid){
        super.sendPaymentRequest(uuid);
        return this.sendHdmRequest()
    }
    sendPaymentCancel(order, uuid) {
        return super.sendPaymentCancel(order, uuid);
    }
    async sendHdmRequest(){

         const order = this.pos.getOrder();
         console.log(order.amount_total, 'AMOUNT')
         console.log(order.getSelectedPaymentline())
         console.log(order.priceIncl, 'priceIncl')
         const paymentLine = this.pos.getOrder().getSelectedPaymentline();
         console.log('HDM payment line', paymentLine);
//         paymentLine.setPaymentStatus('done')
//         return true
         if (paymentLine.amount !== order.priceIncl){
            this._showError('Payment line amount must be equal to order total amount when use HDM fiscal printer')
         }
//         const result = await this.env.services.orm.call("pos.payment.method", "hdm_payment_request", [[this.payment_method_id.id]] )
    }
    _showError(error_msg) {
        this.env.services.dialog.add(AlertDialog, {
            title: "Fiscal Printer Error",
            body: error_msg,
        });
    }
}

register_payment_method('hdm', HdmPaymentArmeniaPos);