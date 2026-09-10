# ERCOT Demand-Side Value Model

A Python financial model that estimates the commercial value of enrolling a
flexible C&I (commercial/industrial) customer's curtailable load into ERCOT
demand-side programs. Built as a portfolio piece for the DER/BESS energy
industry.

## What it models

Given a customer's curtailable load (MW), a forecast accuracy assumption,
and an assumed market condition, the model estimates three independent
annual value streams and nets them against program costs:

1. **4CP transmission charge avoidance** — savings from curtailing load
   during ERCOT's four coincident peak (4CP) intervals, which set a Load
   Serving Entity's transmission cost allocation for the following year.
   This value is forecast-dependent: intervals aren't known until after
   the fact, so missing one loses that interval's share of value entirely
   (a step function over the four intervals, not a smooth discount).
2. **Ancillary services revenue** — combined ERS/RRS/ECRS capacity
   payments for keeping the load available to respond to grid emergencies.
   This is an ongoing capacity payment, not tied to any specific peak
   interval, so it is unaffected by forecast accuracy.
3. **Real-time price spike avoidance** — savings from curtailing during
   ERCOT real-time market scarcity pricing events. This swings
   significantly with grid conditions year to year (extreme
   weather/tight reserves vs. a mild year), so it is modeled by market
   condition (weak/base/strong).

Program costs are a flat aggregator platform fee plus a revenue share
applied only to ancillary services and real-time avoidance revenue — 4CP
avoidance is a passive reduction in the customer's own transmission bill,
not a market-settled payment the aggregator facilitates, so it isn't
shared.

See the docstrings in `src/ercot_demand_value.py` for the real-world
mechanics behind each calculation.

## Project structure

```
ercot-demand-value-model/
├── data/                     # ERCOT market data CSVs (4CP history, AS prices, RTM prices) — added later
├── src/
│   ├── ercot_demand_value.py # Calculation engine
│   └── main.py                # Sample scenario runner + JSON export
├── tests/
│   └── test_ercot_demand_value.py
├── output/                   # Generated results (CSV/JSON) — gitignored, regenerate via main.py
├── requirements.txt
└── README.md
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run the sample scenario (5 MW curtailable load, 75% forecast accuracy,
base market condition):

```bash
python -m src.main
```

This prints a summary of gross value, program costs, and net value, and
writes the result to `output/sample_scenario_result.json`.

## Tests

```bash
python -m unittest discover tests
```

## Rate assumptions

Default rates in `ProgramRates` (see `src/ercot_demand_value.py`) are
illustrative placeholders sized to real ERCOT market magnitudes, not
sourced from a specific settlement year. Once historical ERCOT data (4CP
settlement values, AS clearing prices, RTM price history) is added to
`/data`, those CSVs should replace the defaults.

## Status

Calculation core and unit tests are complete. Data ingestion from `/data`
CSVs and a dashboard front end are not yet built.
