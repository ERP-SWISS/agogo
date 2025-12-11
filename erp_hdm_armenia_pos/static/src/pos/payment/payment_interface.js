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
        order.getSelectedPaymentline().setPaymentStatus('retry')
        super.sendPaymentCancel(order, uuid);
        return new Promise((resolve) => {resolve(true)});
    }

    async sendHdmRequest(){
         const order = this.pos.getOrder();
         const paymentLine = order.getSelectedPaymentline();
         if (paymentLine.amount !== order.priceIncl){
            this._showError('Payment line amount must be equal to order total amount when use HDM fiscal printer')
         }
         let refunded_lines = []
         for (const line of order.lines) {
                console.log(line.serializeForORM())
                console.log(line.serializeForORM()?.refunded_orderline_id)
                refunded_lines.push(line.serializeForORM()?.refunded_orderline_id)
         }

         let result = {}
         const lines = order.lines.map(line => line.serializeForORM())
         if (order.is_refund){
            result = await this.env.services.orm.call("pos.payment.method", "hdm_pos_payment_refund", [[this.payment_method_id.id], this.pos.config.id, paymentLine.amount, refunded_lines, lines])
         } else {
            result = await this.env.services.orm.call("pos.payment.method", "hdm_pos_payment_request", [[this.payment_method_id.id], this.pos.config.id, paymentLine.amount, lines])
         }
         try {
             if ("success" in result){
                 order.fiscal_uuid = result.fiscal_uuid
                 order.fiscal_receipt_id = result.fiscal_receipt_id
                 paymentLine.setPaymentStatus('done')
                return true
             } else {
                paymentLine.setPaymentStatus("retry");
             }
         } catch (error){
            paymentLine.setPaymentStatus("retry");
         }


    }
    _showError(error_msg) {
        this.env.services.dialog.add(AlertDialog, {
            title: "Fiscal Printer Error",
            body: error_msg,
        });
    }
}

register_payment_method('hdm', HdmPaymentArmeniaPos);