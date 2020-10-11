# "Opening Gap" Strategy

In this example, we'll re-create the famous "opening gap" strategy, where we'll go LONG whenever today's open (based on premarket data, 5 minutes before market open) is more than 1% higher than previous day's close.

> ⚠️ You can download the example code listed here from [this Github repository](https://github.com/tradologics/demo-strategy).

## Generating a Token

In order to communicate with Tradologics' cloud, we need to generate an authentication token and use it in our strategy.

```bash
$ tctl token new

To create a new token, please make sure that you
have your API Key and Secret Key handy.

[?] API Key     : ************
[?] API Secret  : ***************************
[?] Token name: demo token
[?] Time-to-live (seconds from now to expire) - optional: 84600

Creating token...

SUCCESS 🎉

The token was created successfully!

Name:       demo token
Expiration: 2050-12-31T00:00:00.000Z
Token:      eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1IjoiYmY3ZTY2ZmEtMmQ4Yy0
0ODI4LTlhNDAtMWVlNmMyNGMzNWVmIiwidCI6MzksImlhdCI6MTYwMjQ0NjAwOSwiZXhwIjo5NTU
yMTQwMzY0MzZ9.DUjBRYzwOkC4QXPpLzklR2ql0GzUJSi_p9bmqEQJJE8

```

## Create a paper account

Next, we'll register a our (paper) account we created with [Alpaca](https://alpaca.markets/). We'll send our orders to that broker.

```
$ tctl accounts new

[?] Account name: My Paper Account
[?] Please select broker: Alpaca
 > Alpaca
   Binance
   Bitfinex
   Bitmex
   Interactive Brokers
   Oanda
   Tradologics

[?] Use broker's paper account (Y/n): y
[?] Key: ********************
[?] Secret: ****************************************

SUCCESS 🎉

The broker account `my-paper-account` (Alpaca) was added to your account.

+-------------------------+-------------------+
| Account                 | 24********81      |
| Cash                    | 100084.15         |
| Equity                  | 100084.15         |
| Initial Margin          | 0                 |
| Maintenance Margin      | 0                 |
| SMA                     | 0                 |
| Currency                | USD               |
| Daytrade Count          | 1                 |
| Pattern Day Trader      | No                |
| RegT Buying Power       | 200168.3          |
| Daytrading Buying Power | 400336.6          |
| Shorting Enabled        | Yes               |
| Multiplier              | 4                 |
| Status                  | ACTIVE            |
| Blocked                 | No                |
| Buying Power            | 400336.6          |
| Positions Market Value  | 0                 |
| Unrealized P&L          | 0                 |
| Realized P&L            | 0                 |
| Account ID              | my-paper-account  |
| Broker                  | alpaca            |
| Name                    | My Paper Alpaca   |
+-------------------------+-------------------+

```

---

## The Strategy

The below strategy is coded in Python - but it should be a straightforward process to convert or re-write it in any language. 

The first thing we'll do is import `tradologics` version of the `requests` library, and its `helper` library. 

> 💡 **NOTE:** 
>
> There's no Tradologic-specific "magic" in this library! This library is simply a wrapper for the awesome `requests` library that will automatically:
>
> 1. Prepend the full url to the API endpoints
> 2. Attach your token to the request headers
> 3. Add datetime to your order when in backtesting mode
>
> The helper library has a function that converts the `bars` Tradehook payload into a Pandas dataframe. That's it.
>
> If you'd rather use your own libraries - go right ahead :)

So let's import the library and set our API Token:

### The "strategy" function

```python
from tradologics import requests, helpers

GAP_THRESHOLD_PCT = 0.01  # min. gap percent

MY_STRATEGY_ID = "opening-gap"
MY_BROKER_ID = "my-paper-account"
MY_TOKEN = "eyJhbGciOiJIU*****9bmqEQJJE8"

# assign token
requests.set_token(MY_TOKEN)

# main strategy function
def strategy(tradehook, payload):
  if tradehook == "bar":
    # Send bar tradehoks to `bar_handler`
    bar_handler(payload)

  elif tradehook == "order":
    # Send order tradehoks to `order_handler`
    order_handler(payload)
```

### Handling bar data

Our strategy will receive data for the assets that we'll specify in our Tradehook (see below), and we'll need to convert it Pandas DataFrame for easier calculation for generating our signal.

We will submit an order whenever today's open (based on premarket data, 5 minutes before maket open) is higher than previous trading day's close.


```python
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
    gap = bars[asset]["o"] / bars[asset]["c"].shift(1) - 1
    gap = gap[-1]  # series' last value
    
    # submit a "market-on-open" order if the gap is > threshold
    if gap >= GAP_THRESHOLD_PCT:
      requests.post("/orders", json={
        "account_id": MY_BROKER_ID,
        "strategy_id": MY_STRATEGY_ID,
        "asset": asset,
        "qty": 100,
        "side": "buy",
        "comment": f"Gap was {gap} from previous open",
        "tif": "opg"  # ← Makret/Limit On-Open
      })

```

### Handling order fills

```python
def order_handler(order):
  """
  Check if the order we're getting notified of is 
  our "entry" order. In this case, submit a market-on-close order.
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
    "side": "sell" if order.get("side") == "long" else "buy",
    "comment": "Submitting a market-on-close order",
    "tif": "cls"  # ← Makret-On-Close
  })
```

That's it :)

### Installing dependencies

Since we're using the `tradologics` library, we need to create a `requirements.txt` to tell Tradologics to install this library for us so we can import it when on the cloud.

Our `requirements.txt` should look something liks:

```
tradologics>=0.0.5
```


### Deploying the strategy

Now that we have our strategy code, let's create it an deploy it to Tradologics servers as a Tradelet (serverless trading function).

Let's create a strategy:

```
❯ tctl strategies new

[?] Strategy name: Opening gap
[?] Description (leave blank for none):
[?] Mode: Broker
   Backtest
   Paper
 > Broker

[?] Host strategy on Tradologics? (Y/n): Y

SUCCESS 🎉

The strategy `Opening gap` (broker) was added to your account.

+-------------+-------------+
| Name        | Opening gap |
| Strategy ID | opening-gap |
| Description | ?           |
| As Tradelet | Yes         |
| Mode        | Broker      |
+-------------+-------------+
```


```basg
$ tctl strategies deploy --strategy opening-gap

[?] Language: Python 3
 > Python 3
   Python 2
   Node
   Go
   C-Sharp
   PHP
   Ruby
   Go
   Java 8
   Java 11
[?] Path to `strategy.py`: ~/gap/strategy.py
[?] Found dependencies file `~/gap/requirements.txt`. Import it? (Y/n):
[?] Comment (optional):

SUCCESS 🎉

Strategy code (v0.1) was deployed successfully.

NOTE: If you haven't already, attach a Tradehook
to this strategy and start your strategy using:

$ tctl strategies start --strategy opening-gap
```

If we'll try to start the strategy now, well get an error message telling us that we cannot run a strategy without any Tradehooks attached.

```bash
$ tctl strategies start --strategy opening-gap

FAILED (status code 400):

{
 "id": "invalid_request",
 "message": "Please create at least one Tradehook that's associated with this strategy"
}
```

So, our next step would be to create a Tradehook and attach it to our strategy.

---

## The Tradehook

For this example, we'll create a Tradehook with the following properties:

- **WHAT**: Two 1-day bars of selected indicies ETFs
- **WHEN**: Every weekday, 5 minutes before the open

The `.yaml` configuration file should look something like this:

### Configuration file

```yaml
---
# Tradehook config file (Tradologics)
what:
  assets:
  - SPY:US
  - QQQ:US
  - IWM:US
  - DIA:US
  - VTI:US
  bar: 1day
  history: 2
when:
  schedule:
    on_days:
    - mon
    - tue
    - wed
    - thu
    - fri
    exchange: XNYS
    session:
      open: -5
      close: 0
    timing: 1day
```

In `JSON` it would look like this:

```json
{
  "what": {
    "assets": ["SPY:US", "QQQ:US", "IWM:US", "DIA:US", "VTI:US"],
    "bar": "1day",
    "history": 2
  },
  "when": {
    "schedule": {
      "on_days": ["mon", "tue", "wed", "thu", "fri"],
      "exchange": "XNYS",
      "session": {
        "open": -5,
        "close": 0
      },
      "timing": "1day"
    }
  }
}
```

### Creating the Tradehook 

Let's create our Tradehook:

```
$ tctl tradehooks new

[?] Tradehook name: opening gap
[?] Path to Tradehook configuration file: ~/gap/tradehook.yaml
[?] Attach to strategy/ies:
 > [X] Oopening gap
[?] Comment (optional): demo strategy

SUCCESS 🎉

The Tradehook `opening gap` was added to your account.
It was attached to:
  - opening-gap
```

Great! 

## Running the strategy 

We now have a strategy with a Tradehook attached to it. All we have left to do is start the strategy using:

```
$ tctl strategies start --strategy opening-gap

SUCCESS 🎉

Tradelet deploy initialized...

  - Check status using `tctl strategies status --strategy opening-gap`
  - Deploy log is available via `tctl strategies log --strategy opening-gap`
```

### Monitoring the strategy

We can check the strategy's status using:

```
$ tctl strategies status --strategy opening-gap

Status: Deploying
```

Let's give it a minute or so and try again:

```
$ tctl strategies status --strategy opening-gap

Status: Running
```

We can now check the orders, positions, etc, using:

```
$ tctl positions ls --strategy opening-gap
$ tctl trades ls --strategy opening-gap
$ tctl orders ls --strategy opening-gap
```

Best of luck! 💪

---

## Conclusion

We've seen how simple it can be to launch a trading strategy on Tradologics' cloud platform.

As always, our team and I are here for every question or idea you'd like to share - so don’t hesitate to contact us by sending an email to accounts@tradologics.com or using the chat box on [beta.tradologics.com](https://beta.tradologics.com).

