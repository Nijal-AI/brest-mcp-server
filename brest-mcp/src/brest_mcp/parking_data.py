"""
Module pour récupérer et traiter les données de stationnement de Brest métropole.
"""
import os
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

# URL de l'API des parkings de Brest métropole
PARKINGS_URL = os.getenv("BREST_PARKINGS_URL", "https://applications002.brest-metropole.fr/VIPDU72/GPB/wms?service=WFS&version=1.1.0&request=GetFeature&typename=GPB_WFS_PARKINGS&outputFormat=application/json")
PARKINGS_REALTIME_URL = os.getenv("BREST_PARKINGS_REALTIME_URL", "https://applications002.brest-metropole.fr/VIPDU72/GPB/wms?service=WFS&version=1.1.0&request=GetFeature&typename=GPB_WFS_PARKINGS_DISPO&outputFormat=application/json")

def fetch_parkings() -> Optional[Dict]:
    """Récupère les données statiques des parkings de Brest métropole."""
    try:
        logging.info(f"Fetching parking data from {PARKINGS_URL}")
        response = requests.get(PARKINGS_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching parking data: {str(e)}")
        return None

def fetch_parkings_availability() -> Optional[Dict]:
    """Récupère les données de disponibilité en temps réel des parkings."""
    try:
        logging.info(f"Fetching parking availability data from {PARKINGS_REALTIME_URL}")
        response = requests.get(PARKINGS_REALTIME_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching parking availability data: {str(e)}")
        return None

def parse_parkings(data: Dict) -> List[Dict]:
    """Parse les données GeoJSON des parkings en liste de dictionnaires."""
    if not data or "features" not in data:
        return []
    
    parkings = []
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        parking = {
            "id": properties.get("id_parking", properties.get("ID_PARKING", "")),
            "name": properties.get("nom", properties.get("NOM", "")),
            "type": properties.get("type", properties.get("TYPE", "")),
            "capacity": properties.get("capacite", properties.get("CAPACITE", 0)),
            "address": properties.get("adresse", properties.get("ADRESSE", "")),
            "payment_method": properties.get("paiement", properties.get("PAIEMENT", "")),
            "opening_hours": properties.get("horaires", properties.get("HORAIRES", "")),
            "coordinates": {
                "latitude": geometry.get("coordinates", [0, 0])[1] if geometry.get("type") == "Point" else 0,
                "longitude": geometry.get("coordinates", [0, 0])[0] if geometry.get("type") == "Point" else 0
            }
        }
        parkings.append(parking)
    
    return parkings

def parse_parkings_availability(data: Dict) -> Dict[str, Dict]:
    """Parse les données de disponibilité des parkings."""
    if not data or "features" not in data:
        return {}
    
    availability = {}
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        parking_id = properties.get("id_parking", properties.get("ID_PARKING", ""))
        
        if parking_id:
            availability[parking_id] = {
                "available_spaces": properties.get("places_disponibles", properties.get("PLACES_DISPONIBLES", 0)),
                "total_spaces": properties.get("capacite", properties.get("CAPACITE", 0)),
                "occupancy_percentage": properties.get("taux_occupation", properties.get("TAUX_OCCUPATION", 0)),
                "status": properties.get("statut", properties.get("STATUT", "UNKNOWN")),
                "last_update": properties.get("derniere_mise_a_jour", properties.get("DERNIERE_MISE_A_JOUR", datetime.now().isoformat()))
            }
    
    return availability

def get_all_parkings_with_availability() -> List[Dict]:
    """Récupère et combine les données statiques et de disponibilité des parkings."""
    parkings_data = fetch_parkings()
    availability_data = fetch_parkings_availability()
    
    parkings = parse_parkings(parkings_data)
    availability = parse_parkings_availability(availability_data)
    
    # Combine les données
    for parking in parkings:
        parking_id = parking.get("id")
        if parking_id in availability:
            parking["availability"] = availability[parking_id]
        else:
            parking["availability"] = {
                "available_spaces": None,
                "total_spaces": parking.get("capacity", 0),
                "occupancy_percentage": None,
                "status": "UNKNOWN",
                "last_update": None
            }
    
    return parkings

def get_parking_by_id(parking_id: str) -> Optional[Dict]:
    """Récupère les informations d'un parking spécifique par son ID."""
    parkings = get_all_parkings_with_availability()
    for parking in parkings:
        if parking.get("id") == parking_id:
            return parking
    return None

def get_parkings_by_type(parking_type: str) -> List[Dict]:
    """Récupère les parkings par type (souterrain, surface, relais, etc.)."""
    parkings = get_all_parkings_with_availability()
    return [p for p in parkings if p.get("type", "").lower() == parking_type.lower()]

def get_nearest_parkings(latitude: float, longitude: float, max_distance: float = 1.0, limit: int = 5) -> List[Dict]:
    """Récupère les parkings les plus proches d'un point géographique."""
    from math import radians, cos, sin, asin, sqrt
    
    def haversine(lon1, lat1, lon2, lat2):
        """Calcule la distance en km entre deux points géographiques."""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        r = 6371  # Rayon de la Terre en km
        return c * r
    
    parkings = get_all_parkings_with_availability()
    parkings_with_distance = []
    
    for parking in parkings:
        coords = parking.get("coordinates", {})
        p_lat = coords.get("latitude", 0)
        p_lon = coords.get("longitude", 0)
        
        if p_lat and p_lon:
            distance = haversine(longitude, latitude, p_lon, p_lat)
            if distance <= max_distance:
                parking["distance"] = distance
                parkings_with_distance.append(parking)
    
    # Trie par distance et limite le nombre de résultats
    parkings_with_distance.sort(key=lambda x: x.get("distance", float("inf")))
    return parkings_with_distance[:limit]
