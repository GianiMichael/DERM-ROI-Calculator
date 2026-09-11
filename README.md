# ERCOT Demand-Side Value Model

**[Live demo — Internal Analysis Dashboard](https://gianimichael.github.io/DERM-ROI-Calculator/dashboard/internal_analysis.html)**

A Python financial model that estimates the commercial value of enrolling a
flexible C&I (commercial/industrial) customer's curtailable load into ERCOT
demand-side programs — built as a DER/BESS commercial revenue modeling
portfolio piece to demonstrate how a flexible load's value stack (peak
charge avoidance, grid services revenue, energy price arbitrage) actually
gets priced and pitched in practice.

## What it calculates

Given a curtailable load (MW), a forecast accuracy assumption, and a market
condition, the engine (`src/ercot_demand_value.py`) estimates three
independent annual value streams:

1. **4CP transmission charge avoidance** — savings from curtailing during
   ERCOT's four coincident peak intervals. Modeled as a step function over
   the four intervals (missing one loses that quarter's value entirely),
   not a smooth discount, since the intervals aren't known until after the
   fact.
2. **Ancillary services revenue** — combined ERS/RRS/ECRS capacity
   payments for staying enrolled and available. An ongoing payment,
   unaffected by forecast accuracy.
3. **Real-time price spike avoidance** — savings from curtailing during
   scarcity-priced RTM intervals. Swings with market condition
   (weak/base/strong) since price volatility varies significantly year to
   year.

Program costs are a flat platform fee plus a 15% revenue share applied only
to ancillary services and RT avoidance (4CP avoidance is a passive bill
reduction, not a market-settled payment the aggregator facilitates). See
each function's docstring in `src/ercot_demand_value.py` for the real-world
mechanic behind it, not just the formula.

## Dashboards

Two self-contained HTML files in `/dashboard`, both driven by a JS
reimplementation of the same engine logic (kept in sync with the Python
by hand, commented as such):

- **`internal_analysis.html`** — the analyst tool. Live sliders for MW,
  forecast accuracy, and market condition recalculate every stat and chart
  instantly: a revenue-stream breakdown, a 4CP step-function chart across
  forecast-accuracy scenarios, and a weak/base/strong sensitivity range.
- **`customer_proposal.html`** — a static, non-technical proposal template
  (plain-English line items, no ERCOT jargon) for handing to a customer.

The two are connected: internal_analysis.html has a **"Generate Customer
Proposal"** button that takes whatever the sliders are currently set to and
opens a populated version of the proposal template in a new tab, so an
analyst can go from exploring a scenario to a client-ready document in one
click.

## Status

**Real and working:** the calculation engine, its 20-test unit test suite
(`tests/test_ercot_demand_value.py`), the sample scenario runner
(`src/main.py`), and both dashboards — all verified to produce matching
numbers across Python, JS, and the rendered pages.

**Still an estimate:** the dollar rates in `ProgramRates` (4CP $/MW-year,
AS $/kW-year, RT spike $/kW-year by market condition) are illustrative
placeholders, not sourced from a specific ERCOT settlement year. Real
historical ERCOT data (published via ERCOT's MIS public reports, and via
the open-source `gridstatus` library) was attempted but is currently
**blocked by this development environment's network policy**, which denies
outbound access to `ercot.com` outright — not an ERCOT login wall. No data
has been fabricated or substituted to work around this; the model plainly
runs on documented benchmark estimates until real data can be pulled in
from an environment that can reach ERCOT.

## Running it locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python -m src.main              # sample scenario -> console summary + output/*.json
python -m unittest discover tests
```

Open either file in `/dashboard` directly in a browser — no build step or
server required.
