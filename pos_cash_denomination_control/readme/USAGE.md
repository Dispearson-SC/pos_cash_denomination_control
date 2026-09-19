## Vault Withdrawal Alert

Each Point of Sale configuration with **Advanced Cash Control** enabled can
set a **Vault Withdrawal Threshold** (**Point of Sale > Configuration >
Settings**, Cash Control section). It defaults to `0`, which disables the
alert entirely.

While a session is open, the Point of Sale periodically checks the drawer's
expected cash (opening balance, plus cash sales, plus cash IN/OUT
movements — the same formula the closing screen already uses) against this
threshold:

- The check runs when the Point of Sale loads, after every successful order
  sync, and after every completed cash move.
- The very first time expected cash reaches or exceeds the threshold, a
  non-blocking notification appears: "Vault withdrawal required". It is
  shown only once per crossing — it does not repeat on every later check
  while the drawer stays over threshold.
- A persistent indicator appears in the navbar while a withdrawal is
  required, and disappears once a later check reports the drawer back under
  the threshold.
- While offline, the indicator keeps showing its last known state; it never
  invents a new one without a successful server round-trip.
- The alert never blocks a sale, a cash move, or a session closing — it is
  purely informational.

Clicking the navbar indicator opens the cash-move popup in "Cash Out" mode
with a vault reason preselected: the Point of Sale's default cash-out reason
if it is itself a vault reason, otherwise the first active vault reason (by
sequence), otherwise no preselection. A user without the stock cash-move
permission sees a notification instead of the popup.
