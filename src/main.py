"""
main.py

Runs a sample flexible-load scenario through the ERCOT demand-side value
model, prints a clean summary, and exports the result as JSON to /output
for downstream dashboard use.

Usage:
    python -m src.main
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ercot_demand_value import MarketCondition, ProgramRates, run_scenario

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def print_summary(result: dict) -> None:
    """Print a clean, human-readable summary of a scenario result."""
    inputs = result["inputs"]
    streams = result["revenue_streams"]

    print("=" * 60)
    print("ERCOT FLEXIBLE LOAD — DEMAND-SIDE VALUE SUMMARY")
    print("=" * 60)
    print(f"Curtailable capacity : {inputs['curtailable_mw']:.1f} MW")
    print(f"Forecast accuracy    : {inputs['forecast_accuracy']:.0%}")
    print(f"Market condition     : {inputs['market_condition'].upper()}")
    print("-" * 60)

    stream_labels = {
        "four_cp_avoidance": "4CP transmission charge avoidance",
        "ancillary_services": "Ancillary services (ERS/RRS/ECRS)",
        "rt_price_spike_avoidance": "RT price spike avoidance",
    }
    stream_df = pd.DataFrame(
        [
            {"Revenue Stream": stream_labels[key], "Annual Value ($)": value}
            for key, value in streams.items()
        ]
    )
    stream_df["Annual Value ($)"] = stream_df["Annual Value ($)"].map("{:,.2f}".format)
    print(stream_df.to_string(index=False))

    print("-" * 60)
    print(f"{'Gross value':<35}${result['gross_value']:>15,.2f}")
    print(f"{'Program costs':<35}${result['program_costs']:>15,.2f}")
    print("-" * 60)
    print(f"{'Net value':<35}${result['net_value']:>15,.2f}")
    print("=" * 60)


def export_result(result: dict, output_dir: Path = OUTPUT_DIR) -> Path:
    """Export a scenario result as timestamped JSON to /output."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        **result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output_path = output_dir / "sample_scenario_result.json"
    with output_path.open("w") as f:
        json.dump(payload, f, indent=2)
    return output_path


def main() -> None:
    result = run_scenario(
        curtailable_mw=5.0,
        forecast_accuracy=0.75,
        market_condition=MarketCondition.BASE,
        rates=ProgramRates(),
    )

    print_summary(result)

    output_path = export_result(result)
    print(f"\nResult exported to: {output_path}")


if __name__ == "__main__":
    main()
