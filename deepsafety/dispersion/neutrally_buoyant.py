import math


def puff_dispersion_ground(
    x: float,
    y: float,
    z: float,
    Q: float,
    u: float,
    sigma_y: float,
    sigma_z: float,
) -> float:
    """
    Instantaneous point source concentration at ground level.

    The signature stays aligned with the broader dispersion API even though this
    simple closed-form relation does not use every argument yet.
    """
    del x, u

    try:
        coefficient = Q / ((2 * math.pi) ** 1.5 * sigma_y * sigma_z)
        exponent = -0.5 * ((y / sigma_y) ** 2 + (z / sigma_z) ** 2)
        return coefficient * math.exp(exponent)
    except ZeroDivisionError:
        return 0.0


def calculate_sigma_y(x: float, stability_class: str) -> float:
    """
    Return the lateral dispersion coefficient sigma_y (m).

    The coefficients use a simplified Pasquill-Gifford style correlation.
    """
    coeffs = {
        "A": (0.22, 0.0001),
        "B": (0.16, 0.0001),
        "C": (0.11, 0.0001),
        "D": (0.08, 0.0001),
        "E": (0.06, 0.0001),
        "F": (0.04, 0.0001),
    }
    a, b = coeffs.get(stability_class.upper(), (0.08, 0.0001))
    return a * x ** (1 + b)


def calculate_sigma_z(x: float, stability_class: str) -> float:
    """
    Return the vertical dispersion coefficient sigma_z (m).

    This uses a simplified Pasquill-Gifford style correlation that is suitable
    for lightweight screening calculations.
    """
    stability_class = stability_class.upper()
    coeffs = {
        "A": (0.20, 0.0, 1.0),
        "B": (0.12, 0.0, 1.0),
        "C": (0.08, 0.0002, 0.5),
        "D": (0.06, 0.0015, 0.5),
        "E": (0.03, 0.0003, 1.0),
        "F": (0.016, 0.0003, 1.0),
    }
    a, b, exponent = coeffs.get(stability_class, (0.06, 0.0015, 0.5))
    return a * x / ((1 + b * x) ** exponent)
