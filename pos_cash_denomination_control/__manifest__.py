{
    "name": "POS Cash Denomination Control",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Denomination breakdown, cash-move reasons, vault alerts, and "
                "closing-manager override for Point of Sale cash control.",
    "author": "Caja Boveda",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/pos_cash_move_reason_data.xml",
        "views/res_config_settings_views.xml",
        "views/pos_cash_move_reason_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_cash_denomination_control/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "pos_cash_denomination_control/static/tests/unit/**/*",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
