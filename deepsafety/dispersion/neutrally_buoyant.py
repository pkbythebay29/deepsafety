import math

def puff_dispersion_ground(x, y, z, Q, u, sigma_y, sigma_z):
    """
    Case 1: Instantaneous point source at ground level.
    """
    try:
        coefficient = Q / ( (2 * math.pi) ** 1.5 * sigma_y * sigma_z )
        exponent = -0.5 * ( (y / sigma_y)**2 + (z / sigma_z)**2 )
        return coefficient * math.exp(exponent)
    except ZeroDivisionError:
        return 0.0

def calculate_sigma_y(x, stability_class):
    """
    Returns the lateral dispersion coefficient sigma_y (m).
    Based on Pasquill-Gifford parameters.
    """
    coeffs = {
        'A': (0.22, 0.0001),
        'B': (0.16, 0.0001),
        'C': (0.11, 0.0001),
        'D': (0.08, 0.0001),
        'E': (0.06, 0.0001),
        'F': (0.04, 0.0001),
    }
    a, b = coeffs.get(stability_class.upper(), (0.08, 0.0001))
    return a * x ** (1 + b)
