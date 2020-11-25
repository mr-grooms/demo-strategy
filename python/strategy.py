from tradologics import requests, helpers

# --- edit this ---
GAP_THRESHOLD_PCT = 0.01  # min. gap percent
MY_STRATEGY_ID = "<my-strategy-id>"
MY_BROKER_ID = "<my-account-id>"
MY_TOKEN = "<my-tradologics-token>"
# --- /edit this ---

requests.set_token(MY_TOKEN)


# main strategy function
def strategy(tradehook, payload):
    if tradehook == "bar":
        # Send bar tradehoks to `bar_handler`
        bar_handler(payload)

    elif tradehook == "order":
        # Send order tradehoks to `order_handler`
        order_handler(payload)


def bar_handler(bars):
    """
    convert bars json to pandas dataframe
    (returns a multi-level DataFrame [ASSET→OHLC_DF])
    """
    bars = helpers.to_pandas(bars, group_by="ticker")

    # get list of assets from columns
    assets = list(bars.columns.levels[0])

    # loop over assets' dataframe
    for asset in assets:
        # calculate the gap (`gap` is a Pandas series)
        # during pre-market, the "close" is the latest price ;-)
        gap = bars[asset]["c"] / bars[asset]["c"].shift(1) - 1
        gap = gap[-1]  # series' last value

        # submit a "market-on-open" order if the gap is > threshold
        if gap >= GAP_THRESHOLD_PCT:
            requests.post("/orders", json={
                "account_id": MY_BROKER_ID,
                "strategy_id": MY_STRATEGY_ID,
                "asset": asset,
                "qty": 100,
                "side": "buy",
                "comment": f"Gap was {gap} from previous close",
                "tif": "opg"  # ← Makret/Limit On-Open
            })


def order_handler(order):
    """
    Check if the order we're getting notified of
    is our "entry" order. In this case, submit a
    market-on-close order.
    """
    if order.get("status") != "filled":
        return

    # format asset (produces: SPY:US, DIA:US, etc.)
    asset = "{ticker}:{region}".format(
        ticker=order.get("ticker"),
        region=order.get("region")
    )

    # if this this an exit order fill - do nothing
    position = requests.get("/positions", json={
        "account_id": MY_BROKER_ID,
        "assets": [asset]
    })

    if position.get("qty") == 0:
        return

    # if entry - send a MOC order
    requests.post("/orders", json={
        "account_id": MY_BROKER_ID,
        "strategy_id": MY_STRATEGY_ID,
        "asset": asset,
        "qty": position.get("qty"),
        "side": "sell" if order.get("side") == "buy" else "buy",
        "comment": "Submitting a market-on-close order",
        "tif": "cls"  # ← Makret-On-Close
    })
