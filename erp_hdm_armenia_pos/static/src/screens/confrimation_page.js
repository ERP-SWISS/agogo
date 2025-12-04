

import { Component, onMounted, onWillUnmount, useState, useEffect, onRendered } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(ConfirmationPage.prototype, {

     async printOrder() {
        if (this.selfOrder.config.self_ordering_mode === "kiosk" && this.canPrintReceipt()) {
            try {
                this.isPrinting = true;
                const order = this.confirmedOrder;
                console.log(order);
                const result = await this.printer.print(
                    OrderReceipt,
                    {
                        order: order,
                    },
                    this.printOptions
                );
                if (!this.selfOrder.has_paper) {
                    this.updateHasPaper(true);
                }
                order.nb_print = 1;
                if (order.isSynced && result) {
                    await rpc("/pos_self_order/kiosk/increment_nb_print/", {
                        access_token: this.selfOrder.access_token,
                        order_id: order.id,
                        order_access_token: order.access_token,
                    });
                }
            } catch (e) {
                if (["EPTR_REC_EMPTY", "EPTR_COVER_OPEN"].includes(e.errorCode)) {
                    this.dialog.add(PrintingFailurePopup, {
                        trackingNumber: this.confirmedOrder.tracking_number,
                        message: e.body,
                        close: () => {
                            this.router.navigate("default");
                        },
                    });
                    this.updateHasPaper(false);
                } else {
                    console.error(e);
                }
            } finally {
                window.print();
                this.isPrinting = false;
            }
        }
    }
})