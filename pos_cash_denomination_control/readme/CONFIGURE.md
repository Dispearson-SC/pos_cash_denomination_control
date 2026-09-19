## Cash In

Installing this module disables cash-in operations on every existing Point
of Sale configuration (`allow_cash_in` is set to `False` for all of them).
New Point of Sale configurations also have cash-in off by default.

To re-enable cash-in for a specific Point of Sale:

1. Go to **Point of Sale > Configuration > Settings**.
2. Open the Point of Sale configuration to change.
3. Under the **Cash Control** section (visible only when the "Advanced Cash
   Control" option is enabled for that Point of Sale), turn on **Cash In**.

When cash-in is off, the "Cash In" option is hidden from the cash-move popup
in the Point of Sale UI, and the server also rejects any `try_cash_in_out`
call of type `in` for that session, no matter how it is issued (Point of
Sale UI, direct RPC, or a replayed offline call), until the toggle is turned
back on.

## Cash Move Reasons

Every cash IN and cash OUT operation now requires a reason from the
**Cash Move Reasons** catalog (**Point of Sale > Configuration > Cash Move
Reasons**, manager access only). A reason has a direction (`Out`, `In`, or
`Both`) that restricts which move types it can be used for, and an optional
"Vault" flag that additionally restricts it to cash OUT only.

The module seeds one reason, "Vault" (`Out`, Vault), and sets it as every
Point of Sale's default cash-out reason — including every Point of Sale
configuration that existed before this module was installed. Any
`try_cash_in_out` call without a valid, active, same-company,
direction-compatible reason is rejected before any accounting entry is
created, so a third-party integration calling `try_cash_in_out` directly
must also supply `extras['reason_id']`.
