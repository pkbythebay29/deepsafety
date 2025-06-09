def flammability_limits(temp_c, LFL_20C, UFL_20C):
    """
    Estimate LFL and UFL at a given temperature.
    Based on Le Chatelier’s Principle.
    """
    LFL = LFL_20C * (273.15 + 20) / (273.15 + temp_c)
    UFL = UFL_20C * (273.15 + temp_c) / (273.15 + 20)
    return round(LFL, 3), round(UFL, 3)
