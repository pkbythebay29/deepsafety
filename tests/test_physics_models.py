import pytest

from deepsafety.catalog import run_model
from deepsafety.dispersion.neutrally_buoyant import calculate_sigma_y, calculate_sigma_z
from deepsafety.dispersion_service import solve_dispersion_model
from deepsafety.source_models import solve_source_model


def test_flammability_limits_match_reference_temperature() -> None:
    outputs, _ = run_model(
        "fire.flammability_limits",
        {"temp_c": 20, "lfl_20c": 2.1, "ufl_20c": 9.5},
    )

    assert outputs["lower_flammability_limit"] == pytest.approx(2.1)
    assert outputs["upper_flammability_limit"] == pytest.approx(9.5)


def test_flammability_limits_follow_expected_temperature_trend() -> None:
    cool_outputs, _ = run_model(
        "fire.flammability_limits",
        {"temp_c": 0, "lfl_20c": 2.1, "ufl_20c": 9.5},
    )
    hot_outputs, _ = run_model(
        "fire.flammability_limits",
        {"temp_c": 80, "lfl_20c": 2.1, "ufl_20c": 9.5},
    )

    assert hot_outputs["lower_flammability_limit"] < cool_outputs["lower_flammability_limit"]
    assert hot_outputs["upper_flammability_limit"] > cool_outputs["upper_flammability_limit"]


def test_point_source_heat_flux_follows_inverse_square_behavior() -> None:
    near_outputs, _ = run_model(
        "fire.point_source_heat_flux",
        {
            "distance_m": 20,
            "burning_rate_kg_s": 4.5,
            "heat_of_combustion_kj_kg": 46000,
        },
    )
    far_outputs, _ = run_model(
        "fire.point_source_heat_flux",
        {
            "distance_m": 40,
            "burning_rate_kg_s": 4.5,
            "heat_of_combustion_kj_kg": 46000,
        },
    )

    assert near_outputs["heat_flux_kw_m2"] / far_outputs["heat_flux_kw_m2"] == pytest.approx(
        4.0, rel=1e-5
    )


def test_heat_flux_impact_radius_shrinks_as_threshold_rises() -> None:
    low_threshold_outputs, _ = run_model(
        "fire.point_source_heat_flux_radius",
        {
            "burning_rate_kg_s": 4.5,
            "heat_of_combustion_kj_kg": 46000,
            "impact_threshold_kw_m2": 4.0,
        },
    )
    high_threshold_outputs, _ = run_model(
        "fire.point_source_heat_flux_radius",
        {
            "burning_rate_kg_s": 4.5,
            "heat_of_combustion_kj_kg": 46000,
            "impact_threshold_kw_m2": 12.5,
        },
    )

    assert low_threshold_outputs["impact_radius_m"] > high_threshold_outputs["impact_radius_m"]


def test_dispersion_coefficients_increase_with_distance() -> None:
    sigma_y_100 = calculate_sigma_y(100, "D")
    sigma_y_200 = calculate_sigma_y(200, "D")
    sigma_z_100 = calculate_sigma_z(100, "D")
    sigma_z_200 = calculate_sigma_z(200, "D")

    assert sigma_y_200 > sigma_y_100 > 0
    assert sigma_z_200 > sigma_z_100 > 0


def test_gaussian_puff_centerline_is_higher_than_off_center() -> None:
    centerline_outputs, _ = run_model(
        "dispersion.gaussian_puff_ground",
        {
            "x": 100,
            "y": 0,
            "z": 0,
            "Q": 25,
            "u": 3.5,
            "sigma_y": 8,
            "sigma_z": 6,
        },
    )
    off_center_outputs, _ = run_model(
        "dispersion.gaussian_puff_ground",
        {
            "x": 100,
            "y": 25,
            "z": 0,
            "Q": 25,
            "u": 3.5,
            "sigma_y": 8,
            "sigma_z": 6,
        },
    )

    assert centerline_outputs["concentration"] > off_center_outputs["concentration"]


def test_leak_screening_radius_grows_with_release_mass() -> None:
    smaller_release_outputs, _ = run_model(
        "dispersion.gaussian_puff_screening_radius",
        {
            "released_mass_kg": 30,
            "concentration_threshold_kg_m3": 0.02,
            "stability_class": "D",
        },
    )
    larger_release_outputs, _ = run_model(
        "dispersion.gaussian_puff_screening_radius",
        {
            "released_mass_kg": 60,
            "concentration_threshold_kg_m3": 0.02,
            "stability_class": "D",
        },
    )

    assert larger_release_outputs["impact_radius_m"] > smaller_release_outputs["impact_radius_m"]


def test_conservative_source_mode_increases_gas_release_rate() -> None:
    base = solve_source_model(
        "gas_release",
        {
            "diameter_m": 0.02,
            "upstream_pressure_pa": 5_000_000,
            "downstream_pressure_pa": 101_325,
            "temperature_k": 288.15,
            "heat_capacity_ratio": 1.3,
            "molecular_weight_kg_kmol": 16.04,
            "duration_s": 60,
            "conservative_mode": False,
        },
    )
    conservative = solve_source_model(
        "gas_release",
        {
            "diameter_m": 0.02,
            "upstream_pressure_pa": 5_000_000,
            "downstream_pressure_pa": 101_325,
            "temperature_k": 288.15,
            "heat_capacity_ratio": 1.3,
            "molecular_weight_kg_kmol": 16.04,
            "duration_s": 60,
            "conservative_mode": True,
        },
    )

    assert conservative["release_rate_kg_s"] > base["release_rate_kg_s"]


def test_gaussian_plume_threshold_distance_increases_when_threshold_drops() -> None:
    higher_threshold = solve_dispersion_model(
        "gaussian_plume",
        {
            "release_rate_kg_s": 2.0,
            "wind_speed_m_s": 3.0,
            "x_m": 200,
            "stability_class": "D",
            "threshold_kg_m3": 1e-4,
        },
    )
    lower_threshold = solve_dispersion_model(
        "gaussian_plume",
        {
            "release_rate_kg_s": 2.0,
            "wind_speed_m_s": 3.0,
            "x_m": 200,
            "stability_class": "D",
            "threshold_kg_m3": 1e-5,
        },
    )

    assert lower_threshold["distance_to_threshold_m"] > higher_threshold["distance_to_threshold_m"]
