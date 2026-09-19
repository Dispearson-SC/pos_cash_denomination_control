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
