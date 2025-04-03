import math

def meter_to_degree_resolution(meter_resolution: float, latitude: float) -> (float, float):
    """
    Převádí metrické rozlišení (v metrech) na úhlové rozlišení (v stupních)
    podle dané zeměpisné šířky.
    
    Args:
        meter_resolution: Rozlišení v metrech (velikost pixelu v metrách)
        latitude: Zeměpisná šířka v stupních, kde se výpočet provádí (např. střed rastru)

    Returns:
        Tuple (x_deg, y_deg) kde:
            x_deg: velikost pixelu v zeměpisných délkách (v stupních)
            y_deg: velikost pixelu v zeměpisných šířkách (v stupních)
    """
    # Přibližný počet metrů na jeden stupeň zeměpisné šířky
    meters_per_degree_lat = 111320.0
    y_deg = meter_resolution / meters_per_degree_lat
    # Počet metrů na jeden stupeň zeměpisné délky se liší podle kosinu zeměpisné šířky
    meters_per_degree_lon = meters_per_degree_lat * math.cos(math.radians(latitude))
    if meters_per_degree_lon == 0:
        x_deg = y_deg  # záložní hodnota; v praxi se takový případ neobjeví
    else:
        x_deg = meter_resolution / meters_per_degree_lon
    return x_deg, y_deg

# Příklad použití:
if __name__ == "__main__":
    meter_resolution = 1.0  # například 1m/pixel
    center_latitude = 50.0  # např. střed vaší mapy
    x_deg, y_deg = meter_to_degree_resolution(meter_resolution, center_latitude)
    print(f"Pro {meter_resolution} m/pixel na šířce {center_latitude}°: xRes = {x_deg:.8f}°, yRes = {y_deg:.8f}°")