"""
ercot_demand_value.py

Calculation engine for estimating the commercial value of enrolling a
flexible C&I (commercial/industrial) load into ERCOT demand-side programs.

Three independent value streams are modeled:

1. 4CP transmission charge avoidance      -> calculate_4cp_avoidance()
2. Ancillary services capacity revenue    -> calculate_ancillary_services_revenue()
3. Real-time price spike avoidance        -> calculate_rt_price_spike_avoidance()

Each stream has a distinct real-world payment mechanic and therefore a
distinct sensitivity to the two customer/market inputs the model takes:
forecast accuracy (a demand-response operations concern) and market
condition (a price-volatility/weather concern). See each function's
docstring for the mechanic it represents.

Rate assumptions (ProgramRates) are illustrative placeholders sized to be
representative of real ERCOT market magnitudes. They are the first thing
that should be replaced with actual historical values once ERCOT market
data (4CP settlement history, AS clearing prices, RTM price data) lands in
/data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MarketCondition(str, Enum):
    """
    Qualitative label for a year's ERCOT real-time price volatility.

    ERCOT's real-time market is scarcity-priced: prices are driven by how
    tight grid reserves get, which is dominated by weather (summer heat,
    winter cold snaps) and generation mix year to year. A "strong" year
    (e.g. 2021's Winter Storm Uri, or a hot, low-wind summer) sees far more
    hours near the system-wide offer cap than a mild "weak" year. Because
    this volatility is what a curtailable load is actually monetizing when
    it avoids real-time price spikes, market condition is the swing factor
    for that revenue stream specifically — it does not affect 4CP or
    ancillary services, which are priced by different mechanisms.
    """

    WEAK = "weak"
    BASE = "base"
    STRONG = "strong"


@dataclass(frozen=True)
class ProgramRates:
    """
    Dollar rates and fee terms behind the model. Defaults are illustrative
    placeholders in the right order of magnitude for ERCOT; swap in
    historical/contracted values once real market data is available in
    /data.

    Attributes:
        four_cp_rate_per_mw_year: Avoided transmission cost of service
            (TCOS), in $ per MW of curtailed load per year, from fully
            avoiding all four 4CP intervals.
        ancillary_rate_per_kw_year: Combined ERS + RRS + ECRS capacity
            payment, in $ per kW of enrolled curtailable capacity per year.
        rt_spike_rate_per_kw_year: Avoided real-time energy cost from
            curtailing during price spikes, in $ per kW-year, keyed by
            MarketCondition.
        platform_fee_annual: Flat annual fee charged by the demand-response
            aggregator/platform for enrollment, telemetry, and dispatch,
            independent of performance.
        revenue_share_pct: Fraction (0 to 1) of ancillary services and
            real-time avoidance revenue paid to the aggregator as a
            performance-based share. Per the program's commercial terms,
            4CP avoidance is a customer-retained savings, not shared
            revenue, since the aggregator does not settle that value
            through ERCOT on the customer's behalf.
    """

    four_cp_rate_per_mw_year: float = 60_000.0
    ancillary_rate_per_kw_year: float = 40.0
    rt_spike_rate_per_kw_year: dict = field(
        default_factory=lambda: {
            MarketCondition.WEAK: 15.0,
            MarketCondition.BASE: 30.0,
            MarketCondition.STRONG: 60.0,
        }
    )
    platform_fee_annual: float = 15_000.0
    revenue_share_pct: float = 0.15


ANNUAL_4CP_INTERVALS = 4


def calculate_4cp_avoidance(
    curtailable_mw: float,
    forecast_accuracy: float,
    four_cp_rate_per_mw_year: float,
) -> float:
    """
    Estimate annual transmission charge avoidance from 4-Coincident-Peak
    (4CP) curtailment.

    Real-world mechanic: ERCOT allocates each Transmission Service
    Provider's transmission cost of service (TCOS) to Load Serving
    Entities based on that load's demand during the single 15-minute
    interval of monthly system peak in June, July, August, and September
    — the "four coincident peaks." A customer's share of next year's
    transmission charges is set by its demand in those four specific
    intervals, not by its demand generally. If a flexible load curtails
    during those exact intervals, it permanently lowers its billing
    demand for the following rate year.

    The catch is that the 4CP intervals are only known for certain after
    the fact — ERCOT does not announce "this is a coincident peak
    interval" in real time. A demand-response operator has to forecast
    which of the ~120 summer peak-risk days/intervals are likely
    coincident peaks and curtail preemptively. Get the forecast right and
    the full avoidance is captured; miss an interval and that interval's
    share of value is lost entirely — there's no partial credit for
    curtailing at the wrong time. That is why this value is modeled as a
    step function over the 4 discrete intervals per year (0/4, 1/4, 2/4,
    3/4, 4/4 correctly called), not a smooth multiplier: forecast skill
    only pays off in discrete quarter-year increments, unlike the other
    two revenue streams which are continuous.

    Args:
        curtailable_mw: Curtailable load capacity, in MW.
        forecast_accuracy: Fraction (0 to 1) of the 4 annual 4CP intervals
            the operator is expected to correctly predict and curtail for.
        four_cp_rate_per_mw_year: Avoided TCOS, in $ per MW-year, from
            fully avoiding all four intervals.

    Returns:
        Estimated annual 4CP transmission charge avoidance, in dollars.
    """
    if not 0.0 <= forecast_accuracy <= 1.0:
        raise ValueError("forecast_accuracy must be between 0 and 1")
    if curtailable_mw < 0:
        raise ValueError("curtailable_mw must be non-negative")

    correctly_called_intervals = round(forecast_accuracy * ANNUAL_4CP_INTERVALS)
    full_value = curtailable_mw * four_cp_rate_per_mw_year
    return full_value * (correctly_called_intervals / ANNUAL_4CP_INTERVALS)


def calculate_ancillary_services_revenue(
    curtailable_mw: float,
    ancillary_rate_per_kw_year: float,
) -> float:
    """
    Estimate annual revenue from ancillary services enrollment
    (ERS + RRS + ECRS combined).

    Real-world mechanic: ERS (Emergency Response Service), RRS (Responsive
    Reserve Service), and ECRS (ERCOT Contingency Reserve Service) are
    capacity-based reserve products. A curtailable load enrolls its
    capacity as available to respond to a grid emergency or frequency
    event, and gets paid a clearing-price capacity payment for holding
    that availability across the enrollment period — similar in spirit to
    an insurance retainer. The payment is for being on standby, not for
    the number of actual dispatch events, and ERCOT dispatches these
    reserves rarely. Because the revenue is a function of enrolled MW and
    the prevailing AS clearing price, not of predicting any specific peak
    interval, it does not depend on forecast accuracy the way 4CP
    avoidance does — the load's operations are already correct by simply
    staying enrolled and responding on the rare occasions ERCOT calls.

    Args:
        curtailable_mw: Curtailable load capacity, in MW.
        ancillary_rate_per_kw_year: Combined ERS+RRS+ECRS capacity payment,
            in $ per kW-year.

    Returns:
        Estimated annual ancillary services revenue, in dollars.
    """
    if curtailable_mw < 0:
        raise ValueError("curtailable_mw must be non-negative")

    curtailable_kw = curtailable_mw * 1_000
    return curtailable_kw * ancillary_rate_per_kw_year


def calculate_rt_price_spike_avoidance(
    curtailable_mw: float,
    market_condition: MarketCondition,
    rt_spike_rate_per_kw_year: dict,
) -> float:
    """
    Estimate annual savings from avoiding real-time (RTM) price spikes.

    Real-world mechanic: ERCOT's real-time market is scarcity-priced —
    when operating reserves get thin, prices can spike from typical
    $20-40/MWh levels toward the system-wide offer cap (historically as
    high as $9,000/MWh, now governed by ERCOT's ORDC/ASDC scarcity
    pricing adders). A load that can curtail during those spike intervals
    avoids paying settlement prices at the spike, capturing the delta as
    savings versus a static, non-flexible load shape.

    How much this is worth swings enormously year to year because it's a
    function of grid tightness, not of the customer's own behavior:
    hot, low-wind summers or extreme winter cold snaps (e.g. Winter Storm
    Uri, February 2021) drive far more hours of scarcity pricing than a
    mild year with ample reserve margin. That's why this stream — unlike
    ancillary services capacity payments, which clear at comparatively
    stable prices — is modeled as varying by market condition
    (weak/base/strong) rather than being treated as a fixed annual rate.

    Args:
        curtailable_mw: Curtailable load capacity, in MW.
        market_condition: Qualitative label for the year's RTM price
            volatility (MarketCondition.WEAK / BASE / STRONG).
        rt_spike_rate_per_kw_year: Mapping of MarketCondition to avoided
            RTM cost, in $ per kW-year.

    Returns:
        Estimated annual real-time price spike avoidance, in dollars.
    """
    if curtailable_mw < 0:
        raise ValueError("curtailable_mw must be non-negative")
    if market_condition not in rt_spike_rate_per_kw_year:
        raise ValueError(f"Unknown market_condition: {market_condition!r}")

    curtailable_kw = curtailable_mw * 1_000
    rate = rt_spike_rate_per_kw_year[market_condition]
    return curtailable_kw * rate


def calculate_program_costs(
    ancillary_revenue: float,
    rt_avoidance_revenue: float,
    platform_fee_annual: float,
    revenue_share_pct: float,
) -> float:
    """
    Estimate the annual cost of running the flexible load through a
    demand-response aggregator/platform.

    Real-world mechanic: aggregators typically charge a flat platform fee
    covering enrollment, telemetry/metering, and dispatch operations, plus
    a performance-based revenue share on the revenue streams they actively
    help settle through ERCOT markets (ancillary services bids, real-time
    dispatch optimization). 4CP avoidance is excluded from the revenue
    share here because it is not a market-settled payment the aggregator
    facilitates — it is a passive reduction in the customer's own
    transmission bill that the customer captures directly.

    Args:
        ancillary_revenue: Annual ancillary services revenue, in dollars.
        rt_avoidance_revenue: Annual real-time price spike avoidance, in
            dollars.
        platform_fee_annual: Flat annual aggregator platform fee, in
            dollars.
        revenue_share_pct: Fraction (0 to 1) of ancillary + RT avoidance
            revenue paid to the aggregator.

    Returns:
        Total estimated annual program cost, in dollars.
    """
    if not 0.0 <= revenue_share_pct <= 1.0:
        raise ValueError("revenue_share_pct must be between 0 and 1")

    shared_revenue_base = ancillary_revenue + rt_avoidance_revenue
    revenue_share_cost = shared_revenue_base * revenue_share_pct
    return platform_fee_annual + revenue_share_cost


def run_scenario(
    curtailable_mw: float,
    forecast_accuracy: float,
    market_condition: MarketCondition,
    rates: ProgramRates | None = None,
) -> dict:
    """
    Run all three value calculations plus program costs for a single
    customer scenario and return a structured result.

    Args:
        curtailable_mw: Curtailable load capacity, in MW.
        forecast_accuracy: Fraction (0 to 1) of 4CP intervals correctly
            predicted.
        market_condition: MarketCondition.WEAK / BASE / STRONG.
        rates: ProgramRates to use; defaults to ProgramRates() if omitted.

    Returns:
        Dict with per-stream revenue, gross value, program costs, and net
        value, suitable for JSON serialization.
    """
    rates = rates or ProgramRates()

    four_cp_value = calculate_4cp_avoidance(
        curtailable_mw=curtailable_mw,
        forecast_accuracy=forecast_accuracy,
        four_cp_rate_per_mw_year=rates.four_cp_rate_per_mw_year,
    )
    ancillary_value = calculate_ancillary_services_revenue(
        curtailable_mw=curtailable_mw,
        ancillary_rate_per_kw_year=rates.ancillary_rate_per_kw_year,
    )
    rt_avoidance_value = calculate_rt_price_spike_avoidance(
        curtailable_mw=curtailable_mw,
        market_condition=market_condition,
        rt_spike_rate_per_kw_year=rates.rt_spike_rate_per_kw_year,
    )

    gross_value = four_cp_value + ancillary_value + rt_avoidance_value
    program_costs = calculate_program_costs(
        ancillary_revenue=ancillary_value,
        rt_avoidance_revenue=rt_avoidance_value,
        platform_fee_annual=rates.platform_fee_annual,
        revenue_share_pct=rates.revenue_share_pct,
    )
    net_value = gross_value - program_costs

    return {
        "inputs": {
            "curtailable_mw": curtailable_mw,
            "forecast_accuracy": forecast_accuracy,
            "market_condition": market_condition.value,
        },
        "revenue_streams": {
            "four_cp_avoidance": round(four_cp_value, 2),
            "ancillary_services": round(ancillary_value, 2),
            "rt_price_spike_avoidance": round(rt_avoidance_value, 2),
        },
        "gross_value": round(gross_value, 2),
        "program_costs": round(program_costs, 2),
        "net_value": round(net_value, 2),
    }
