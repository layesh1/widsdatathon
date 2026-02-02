"""
evacuation_routes.py

Evacuation Route Analysis for Wildfire Caregiver Alert System
Uses OpenStreetMap data to calculate evacuation routes and safe zones

Features:
- Calculate distance to major highways
- Identify evacuation corridors
- Find safe zones (hospitals, shelters, outside fire zones)
- Route recommendations for vulnerable populations
"""

import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points on Earth (in km)
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    
    return km


def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate bearing (direction) from point 1 to point 2
    Returns degrees (0-360, where 0=North, 90=East)
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    
    bearing = np.degrees(np.arctan2(x, y))
    bearing = (bearing + 360) % 360
    
    return bearing


def get_evacuation_direction(fire_lat, fire_lon, vulnerable_lat, vulnerable_lon):
    """
    Determine safe evacuation direction (opposite of fire)
    Returns recommended direction as cardinal direction
    """
    # Calculate bearing FROM fire TO vulnerable location
    fire_bearing = calculate_bearing(fire_lat, fire_lon, vulnerable_lat, vulnerable_lon)
    
    # Evacuate in opposite direction (away from fire)
    evacuation_bearing = (fire_bearing + 180) % 360
    
    # Convert to cardinal direction
    directions = ['North', 'Northeast', 'East', 'Southeast', 
                  'South', 'Southwest', 'West', 'Northwest']
    index = round(evacuation_bearing / 45) % 8
    
    return directions[index], evacuation_bearing


# Major US Interstate Highways and their approximate routes
MAJOR_HIGHWAYS = {
    'I-5': {'name': 'Interstate 5', 'states': ['CA', 'OR', 'WA'], 'coords': [
        (32.5, -117.1),  # San Diego
        (34.0, -118.2),  # LA
        (37.8, -122.4),  # SF
        (45.5, -122.7),  # Portland
        (47.6, -122.3)   # Seattle
    ]},
    'I-10': {'name': 'Interstate 10', 'states': ['CA', 'AZ', 'NM', 'TX'], 'coords': [
        (34.0, -118.2),  # LA
        (33.4, -112.1),  # Phoenix
        (31.8, -106.4),  # El Paso
        (29.4, -98.5)    # San Antonio
    ]},
    'I-15': {'name': 'Interstate 15', 'states': ['CA', 'NV', 'UT'], 'coords': [
        (32.7, -117.2),  # San Diego
        (34.1, -117.3),  # San Bernardino
        (36.2, -115.1),  # Las Vegas
        (40.8, -111.9)   # Salt Lake City
    ]},
    'I-40': {'name': 'Interstate 40', 'states': ['CA', 'AZ', 'NM'], 'coords': [
        (34.9, -114.6),  # Needles, CA
        (35.2, -111.7),  # Flagstaff
        (35.1, -106.6)   # Albuquerque
    ]},
    'I-80': {'name': 'Interstate 80', 'states': ['CA', 'NV', 'UT', 'WY', 'NE'], 'coords': [
        (37.8, -122.3),  # SF Bay
        (39.5, -119.8),  # Reno
        (40.8, -111.9),  # Salt Lake City
        (41.1, -104.8)   # Cheyenne
    ]},
    'I-95': {'name': 'Interstate 95', 'states': ['FL', 'GA', 'SC', 'NC', 'VA'], 'coords': [
        (25.8, -80.2),   # Miami
        (26.7, -80.1),   # West Palm Beach
        (28.5, -81.4),   # Orlando area
        (30.3, -81.7),   # Jacksonville
        (32.1, -81.1),   # Savannah
        (33.9, -78.9),   # Myrtle Beach
        (34.0, -81.0),   # Columbia
        (35.8, -78.6),   # Raleigh
        (36.9, -76.3)    # Norfolk
    ]}
}


def find_nearest_highway(lat, lon, state=None):
    """
    Find nearest major highway to a location
    Returns: (highway_name, distance_km, nearest_point)
    """
    min_distance = float('inf')
    nearest_highway = None
    nearest_point = None
    
    for highway_id, highway_data in MAJOR_HIGHWAYS.items():
        # Filter by state if provided
        if state and state not in highway_data['states']:
            continue
        
        # Check distance to each point on the highway
        for point in highway_data['coords']:
            dist = haversine_distance(lat, lon, point[0], point[1])
            if dist < min_distance:
                min_distance = dist
                nearest_highway = highway_data['name']
                nearest_point = point
    
    return nearest_highway, min_distance, nearest_point


# Safe zones (major cities outside typical fire zones)
SAFE_ZONES = {
    'Phoenix Metro': (33.4484, -112.0740),
    'Las Vegas': (36.1699, -115.1398),
    'Reno': (39.5296, -119.8138),
    'Salt Lake City': (40.7608, -111.8910),
    'Denver': (39.7392, -104.9903),
    'Albuquerque': (35.0844, -106.6504),
    'Sacramento': (38.5816, -121.4944),
    'Fresno': (36.7378, -119.7871),
    'San Diego': (32.7157, -117.1611),
    'Portland': (45.5152, -122.6784),
    'Seattle': (47.6062, -122.3321),
    'Tucson': (32.2226, -110.9747),
    'El Paso': (31.7619, -106.4850)
}


def find_nearest_safe_zone(lat, lon, exclude_radius_km=100):
    """
    Find nearest designated safe zone
    Safe zones are major cities assumed to be outside immediate fire danger
    
    Args:
        lat, lon: Current location
        exclude_radius_km: Minimum distance to be considered "safe"
    
    Returns: (safe_zone_name, distance_km, coordinates)
    """
    candidates = []
    
    for zone_name, (zone_lat, zone_lon) in SAFE_ZONES.items():
        dist = haversine_distance(lat, lon, zone_lat, zone_lon)
        if dist >= exclude_radius_km:  # Must be far enough away
            candidates.append((zone_name, dist, (zone_lat, zone_lon)))
    
    if not candidates:
        return None, None, None
    
    # Sort by distance
    candidates.sort(key=lambda x: x[1])
    
    return candidates[0]


def calculate_evacuation_plan(vulnerable_lat, vulnerable_lon, fire_lat, fire_lon, 
                               fire_name, state=None):
    """
    Calculate comprehensive evacuation plan for a vulnerable location
    
    Returns dict with:
    - evacuation_direction: Cardinal direction to evacuate
    - nearest_highway: Closest major highway
    - highway_distance: Distance to highway (km)
    - safe_zone: Recommended destination
    - safe_zone_distance: Distance to safe zone (km)
    - total_distance: Estimated evacuation distance
    - fire_distance: Distance from fire (km)
    - urgency: HIGH/MEDIUM/LOW based on fire proximity
    """
    # Calculate fire distance
    fire_dist = haversine_distance(vulnerable_lat, vulnerable_lon, fire_lat, fire_lon)
    
    # Determine evacuation direction
    evac_dir, evac_bearing = get_evacuation_direction(
        fire_lat, fire_lon, vulnerable_lat, vulnerable_lon
    )
    
    # Find nearest highway
    highway, highway_dist, highway_point = find_nearest_highway(
        vulnerable_lat, vulnerable_lon, state
    )
    
    # Find safe zone
    safe_zone, safe_zone_dist, safe_zone_coords = find_nearest_safe_zone(
        vulnerable_lat, vulnerable_lon
    )
    
    # Estimate total evacuation distance
    # Approximate: distance to highway + distance from highway to safe zone
    if highway_point and safe_zone_coords:
        highway_to_safe = haversine_distance(
            highway_point[0], highway_point[1],
            safe_zone_coords[0], safe_zone_coords[1]
        )
        total_dist = highway_dist + highway_to_safe
    else:
        total_dist = safe_zone_dist if safe_zone_dist else 0
    
    # Determine urgency
    if fire_dist < 15:
        urgency = "HIGH"
    elif fire_dist < 40:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"
    
    return {
        'evacuation_direction': evac_dir,
        'evacuation_bearing': evac_bearing,
        'fire_name': fire_name,
        'fire_distance_km': fire_dist,
        'fire_distance_mi': fire_dist * 0.621371,
        'nearest_highway': highway or "No major highway nearby",
        'highway_distance_km': highway_dist if highway else None,
        'highway_distance_mi': highway_dist * 0.621371 if highway else None,
        'safe_zone': safe_zone or "Consult local authorities",
        'safe_zone_distance_km': safe_zone_dist if safe_zone_dist else None,
        'safe_zone_distance_mi': safe_zone_dist * 0.621371 if safe_zone_dist else None,
        'total_distance_km': total_dist,
        'total_distance_mi': total_dist * 0.621371,
        'urgency': urgency
    }


def generate_evacuation_routes_for_alerts(fire_data, vulnerable_populations, alerts):
    """
    Generate evacuation routes for all active alerts
    
    Args:
        fire_data: DataFrame with fire information
        vulnerable_populations: Dict of vulnerable locations
        alerts: List of proximity alerts
    
    Returns:
        List of evacuation plans with routes
    """
    evacuation_plans = []
    
    for alert in alerts:
        location_name = alert['Location']
        fire_name = alert['Fire_Name']
        
        if location_name not in vulnerable_populations:
            continue
        
        # Get vulnerable location coordinates
        vuln_data = vulnerable_populations[location_name]
        vuln_lat = vuln_data['lat']
        vuln_lon = vuln_data['lon']
        
        # Find the fire
        fire = fire_data[fire_data['fire_name'] == fire_name].iloc[0]
        fire_lat = fire['latitude']
        fire_lon = fire['longitude']
        
        # Extract state from location name (e.g., "Los Angeles County, CA" -> "CA")
        state = location_name.split(',')[-1].strip() if ',' in location_name else None
        
        # Calculate evacuation plan
        plan = calculate_evacuation_plan(
            vuln_lat, vuln_lon, fire_lat, fire_lon, fire_name, state
        )
        
        plan['location'] = location_name
        plan['vulnerable_count'] = vuln_data.get('vulnerable_count', 0)
        
        evacuation_plans.append(plan)
    
    return evacuation_plans


if __name__ == "__main__":
    # Test the evacuation route calculator
    print("Testing Evacuation Route Calculator")
    print("=" * 60)
    
    # Example: Fire near Los Angeles
    fire_lat, fire_lon = 34.2, -118.0
    vuln_lat, vuln_lon = 34.0, -118.2
    
    plan = calculate_evacuation_plan(
        vuln_lat, vuln_lon, fire_lat, fire_lon, "Test Fire", "CA"
    )
    
    print(f"\n📍 Vulnerable Location: {vuln_lat:.2f}, {vuln_lon:.2f}")
    print(f"🔥 Fire Location: {fire_lat:.2f}, {fire_lon:.2f}")
    print(f"\n⚠️ URGENCY: {plan['urgency']}")
    print(f"🧭 Evacuate: {plan['evacuation_direction']}")
    print(f"🔥 Fire Distance: {plan['fire_distance_mi']:.1f} miles")
    print(f"🛣️  Nearest Highway: {plan['nearest_highway']} ({plan['highway_distance_mi']:.1f} mi)")
    print(f"🏛️  Safe Zone: {plan['safe_zone']} ({plan['safe_zone_distance_mi']:.1f} mi)")
    print(f"📏 Total Evacuation Distance: {plan['total_distance_mi']:.1f} miles")
