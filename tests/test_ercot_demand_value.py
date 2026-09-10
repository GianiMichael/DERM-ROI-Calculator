"""Unit tests for the ERCOT demand-side value calculation engine."""

import unittest

from src.ercot_demand_value import (
    MarketCondition,
    ProgramRates,
    calculate_4cp_avoidance,
    calculate_ancillary_services_revenue,
    calculate_program_costs,
    calculate_rt_price_spike_avoidance,
    run_scenario,
)


class TestFourCPAvoidance(unittest.TestCase):
    def test_full_forecast_accuracy_captures_full_value(self):
        value = calculate_4cp_avoidance(
            curtailable_mw=5.0, forecast_accuracy=1.0, four_cp_rate_per_mw_year=60_000.0
        )
        self.assertEqual(value, 5.0 * 60_000.0)

    def test_zero_forecast_accuracy_captures_no_value(self):
        value = calculate_4cp_avoidance(
            curtailable_mw=5.0, forecast_accuracy=0.0, four_cp_rate_per_mw_year=60_000.0
        )
        self.assertEqual(value, 0.0)

    def test_value_steps_in_quarters_not_smoothly(self):
        # 0.6 accuracy rounds to 2/4 correctly-called intervals (0.6 * 4 = 2.4 -> round to 2),
        # not a smooth 60% of full value.
        rate = 60_000.0
        mw = 5.0
        value = calculate_4cp_avoidance(
            curtailable_mw=mw, forecast_accuracy=0.6, four_cp_rate_per_mw_year=rate
        )
        expected = (mw * rate) * (2 / 4)
        self.assertEqual(value, expected)
        self.assertNotEqual(value, (mw * rate) * 0.6)

    def test_three_of_four_intervals(self):
        rate = 60_000.0
        mw = 5.0
        # 0.8 * 4 = 3.2 -> rounds to 3
        value = calculate_4cp_avoidance(
            curtailable_mw=mw, forecast_accuracy=0.8, four_cp_rate_per_mw_year=rate
        )
        expected = (mw * rate) * (3 / 4)
        self.assertEqual(value, expected)

    def test_rejects_out_of_range_forecast_accuracy(self):
        with self.assertRaises(ValueError):
            calculate_4cp_avoidance(
                curtailable_mw=5.0, forecast_accuracy=1.5, four_cp_rate_per_mw_year=60_000.0
            )
        with self.assertRaises(ValueError):
            calculate_4cp_avoidance(
                curtailable_mw=5.0, forecast_accuracy=-0.1, four_cp_rate_per_mw_year=60_000.0
            )

    def test_rejects_negative_capacity(self):
        with self.assertRaises(ValueError):
            calculate_4cp_avoidance(
                curtailable_mw=-1.0, forecast_accuracy=1.0, four_cp_rate_per_mw_year=60_000.0
            )

    def test_zero_capacity_yields_zero_value(self):
        value = calculate_4cp_avoidance(
            curtailable_mw=0.0, forecast_accuracy=1.0, four_cp_rate_per_mw_year=60_000.0
        )
        self.assertEqual(value, 0.0)


class TestAncillaryServicesRevenue(unittest.TestCase):
    def test_scales_linearly_with_capacity(self):
        value = calculate_ancillary_services_revenue(
            curtailable_mw=5.0, ancillary_rate_per_kw_year=40.0
        )
        self.assertEqual(value, 5.0 * 1_000 * 40.0)

    def test_unaffected_by_forecast_accuracy(self):
        # Ancillary services revenue has no forecast_accuracy parameter at all —
        # this test documents that omission is intentional, not an oversight.
        value_a = calculate_ancillary_services_revenue(
            curtailable_mw=5.0, ancillary_rate_per_kw_year=40.0
        )
        value_b = calculate_ancillary_services_revenue(
            curtailable_mw=5.0, ancillary_rate_per_kw_year=40.0
        )
        self.assertEqual(value_a, value_b)

    def test_rejects_negative_capacity(self):
        with self.assertRaises(ValueError):
            calculate_ancillary_services_revenue(
                curtailable_mw=-2.0, ancillary_rate_per_kw_year=40.0
            )


class TestRTPriceSpikeAvoidance(unittest.TestCase):
    def setUp(self):
        self.rates = ProgramRates().rt_spike_rate_per_kw_year

    def test_strong_year_exceeds_base_exceeds_weak(self):
        weak = calculate_rt_price_spike_avoidance(5.0, MarketCondition.WEAK, self.rates)
        base = calculate_rt_price_spike_avoidance(5.0, MarketCondition.BASE, self.rates)
        strong = calculate_rt_price_spike_avoidance(5.0, MarketCondition.STRONG, self.rates)
        self.assertLess(weak, base)
        self.assertLess(base, strong)

    def test_scales_linearly_with_capacity(self):
        value = calculate_rt_price_spike_avoidance(10.0, MarketCondition.BASE, self.rates)
        self.assertEqual(value, 10.0 * 1_000 * self.rates[MarketCondition.BASE])

    def test_rejects_unknown_market_condition(self):
        with self.assertRaises(ValueError):
            calculate_rt_price_spike_avoidance(5.0, "extreme", self.rates)

    def test_rejects_negative_capacity(self):
        with self.assertRaises(ValueError):
            calculate_rt_price_spike_avoidance(-1.0, MarketCondition.BASE, self.rates)


class TestProgramCosts(unittest.TestCase):
    def test_revenue_share_applies_only_to_ancillary_and_rt(self):
        costs = calculate_program_costs(
            ancillary_revenue=100_000.0,
            rt_avoidance_revenue=50_000.0,
            platform_fee_annual=15_000.0,
            revenue_share_pct=0.15,
        )
        expected = 15_000.0 + (100_000.0 + 50_000.0) * 0.15
        self.assertEqual(costs, expected)

    def test_platform_fee_charged_even_with_zero_revenue(self):
        costs = calculate_program_costs(
            ancillary_revenue=0.0,
            rt_avoidance_revenue=0.0,
            platform_fee_annual=15_000.0,
            revenue_share_pct=0.15,
        )
        self.assertEqual(costs, 15_000.0)

    def test_rejects_out_of_range_revenue_share(self):
        with self.assertRaises(ValueError):
            calculate_program_costs(
                ancillary_revenue=1.0,
                rt_avoidance_revenue=1.0,
                platform_fee_annual=1.0,
                revenue_share_pct=1.5,
            )


class TestRunScenario(unittest.TestCase):
    def test_sample_scenario_end_to_end(self):
        result = run_scenario(
            curtailable_mw=5.0,
            forecast_accuracy=1.0,
            market_condition=MarketCondition.BASE,
            rates=ProgramRates(),
        )
        streams = result["revenue_streams"]
        expected_gross = (
            streams["four_cp_avoidance"]
            + streams["ancillary_services"]
            + streams["rt_price_spike_avoidance"]
        )
        self.assertAlmostEqual(result["gross_value"], expected_gross, places=2)
        self.assertAlmostEqual(
            result["net_value"], result["gross_value"] - result["program_costs"], places=2
        )

    def test_4cp_avoidance_excluded_from_program_cost_base(self):
        # Full forecast accuracy maximizes 4CP value; if it leaked into the
        # revenue-share base, program costs would scale with it too.
        result_low_forecast = run_scenario(
            curtailable_mw=5.0,
            forecast_accuracy=0.0,
            market_condition=MarketCondition.BASE,
        )
        result_high_forecast = run_scenario(
            curtailable_mw=5.0,
            forecast_accuracy=1.0,
            market_condition=MarketCondition.BASE,
        )
        self.assertEqual(
            result_low_forecast["program_costs"], result_high_forecast["program_costs"]
        )

    def test_default_rates_used_when_none_provided(self):
        result = run_scenario(
            curtailable_mw=1.0,
            forecast_accuracy=0.5,
            market_condition=MarketCondition.WEAK,
        )
        self.assertIn("gross_value", result)
        self.assertIn("net_value", result)


if __name__ == "__main__":
    unittest.main()
