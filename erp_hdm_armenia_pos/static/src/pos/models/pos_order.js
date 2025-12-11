import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setup() {
        super.setup(...arguments);
    },
    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        if (this.fiscal_receipt_id && !data.fiscal_receipt_id) {
            data.fiscal_receipt_id = this.fiscal_receipt_id;
        }
        return data;
    },
});
