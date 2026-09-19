import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { VaultAlertIndicator } from "@pos_cash_denomination_control/app/components/navbar/vault_alert_indicator/vault_alert_indicator";

patch(Navbar, {
    components: { ...Navbar.components, VaultAlertIndicator },
});
