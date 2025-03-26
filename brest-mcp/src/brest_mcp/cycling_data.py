"""
Module pour récupérer et traiter les données de vélos et mobilité douce pour Brest.
"""
import os
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

# URLs des APIs pour les données de vélos
CYCLING_INFRASTRUCTURE_URL = os.getenv("CYCLING_INFRASTRUCTURE_URL", 
                                     "https://applications002.brest-metropole.fr/VIPDU72/GPB/wms?service=WFS&version=1.1.0&request=GetFeature&typename=GPB_WFS_AMENAGEMENT_CYCLABLE&outputFormat=application/json")
BIKE_PARKING_URL = os.getenv("BIKE_PARKING_URL", 
                           "https://applications002.brest-metropole.fr/VIPDU72/GPB/wms?service=WFS&version=1.1.0&request=GetFeature&typename=GPB_WFS_STATIONNEMENT_VELO&outputFormat=application/json")

def fetch_cycling_infrastructure() -> Optional[Dict]:
    """
    Récupère les données d'infrastructures cyclables de Brest métropole.
    
    Returns:
        Données d'infrastructures cyclables ou None en cas d'erreur
    """
    try:
        logging.info(f"Fetching cycling infrastructure data from {CYCLING_INFRASTRUCTURE_URL}")
        response = requests.get(CYCLING_INFRASTRUCTURE_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching cycling infrastructure data: {str(e)}")
        return None

def fetch_bike_parking() -> Optional[Dict]:
    """
    Récupère les données de stationnements vélo de Brest métropole.
    
    Returns:
        Données de stationnements vélo ou None en cas d'erreur
    """
    try:
        logging.info(f"Fetching bike parking data from {BIKE_PARKING_URL}")
        response = requests.get(BIKE_PARKING_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching bike parking data: {str(e)}")
        return None

def parse_cycling_infrastructure(data: Dict) -> List[Dict]:
    """
    Parse les données GeoJSON des infrastructures cyclables.
    
    Args:
        data: Données brutes GeoJSON
    
    Returns:
        Liste des infrastructures cyclables formatées
    """
    if not data or "features" not in data:
        return []
    
    infrastructure = []
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        infra = {
            "id": properties.get("id", properties.get("ID", "")),
            "type": properties.get("type_amenagement", properties.get("TYPE_AMENAGEMENT", "")),
            "name": properties.get("nom", properties.get("NOM", "")),
            "length": properties.get("longueur", properties.get("LONGUEUR", 0)),
            "bidirectional": properties.get("bidirectionnel", properties.get("BIDIRECTIONNEL", False)),
            "status": properties.get("statut", properties.get("STATUT", "")),
            "geometry": geometry
        }
        infrastructure.append(infra)
    
    return infrastructure

def parse_bike_parking(data: Dict) -> List[Dict]:
    """
    Parse les données GeoJSON des stationnements vélo.
    
    Args:
        data: Données brutes GeoJSON
    
    Returns:
        Liste des stationnements vélo formatés
    """
    if not data or "features" not in data:
        return []
    
    parkings = []
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        parking = {
            "id": properties.get("id", properties.get("ID", "")),
            "type": properties.get("type", properties.get("TYPE", "")),
            "capacity": properties.get("capacite", properties.get("CAPACITE", 0)),
            "covered": properties.get("couvert", properties.get("COUVERT", False)),
            "secured": properties.get("securise", properties.get("SECURISE", False)),
            "address": properties.get("adresse", properties.get("ADRESSE", "")),
            "coordinates": {
                "latitude": geometry.get("coordinates", [0, 0])[1] if geometry.get("type") == "Point" else 0,
                "longitude": geometry.get("coordinates", [0, 0])[0] if geometry.get("type") == "Point" else 0
            }
        }
        parkings.append(parking)
    
    return parkings

def get_all_bike_parkings() -> List[Dict]:
    """
    Récupère tous les stationnements vélo.
    
    Returns:
        Liste des stationnements vélo
    """
    data = fetch_bike_parking()
    if not data:
        return []
    
    return parse_bike_parking(data)

def get_bike_parking_by_id(parking_id: str) -> Optional[Dict]:
    """
    Récupère un stationnement vélo par son ID.
    
    Args:
        parking_id: ID du stationnement vélo
    
    Returns:
        Informations sur le stationnement vélo ou None s'il n'existe pas
    """
    parkings = get_all_bike_parkings()
    for parking in parkings:
        if parking.get("id") == parking_id:
            return parking
    return None

def get_bike_parkings_by_type(parking_type: str) -> List[Dict]:
    """
    Récupère les stationnements vélo par type.
    
    Args:
        parking_type: Type de stationnement vélo
    
    Returns:
        Liste des stationnements vélo du type spécifié
    """
    parkings = get_all_bike_parkings()
    return [p for p in parkings if p.get("type", "").lower() == parking_type.lower()]

def get_secured_bike_parkings() -> List[Dict]:
    """
    Récupère tous les stationnements vélo sécurisés.
    
    Returns:
        Liste des stationnements vélo sécurisés
    """
    parkings = get_all_bike_parkings()
    return [p for p in parkings if p.get("secured", False)]

def get_covered_bike_parkings() -> List[Dict]:
    """
    Récupère tous les stationnements vélo couverts.
    
    Returns:
        Liste des stationnements vélo couverts
    """
    parkings = get_all_bike_parkings()
    return [p for p in parkings if p.get("covered", False)]

def get_cycling_routes() -> List[Dict]:
    """
    Récupère toutes les pistes cyclables.
    
    Returns:
        Liste des pistes cyclables
    """
    data = fetch_cycling_infrastructure()
    if not data:
        return []
    
    return parse_cycling_infrastructure(data)

def get_cycling_routes_by_type(route_type: str) -> List[Dict]:
    """
    Récupère les pistes cyclables par type.
    
    Args:
        route_type: Type de piste cyclable
    
    Returns:
        Liste des pistes cyclables du type spécifié
    """
    routes = get_cycling_routes()
    return [r for r in routes if r.get("type", "").lower() == route_type.lower()]

def get_nearest_bike_parkings(latitude: float, longitude: float, max_distance: float = 1.0, limit: int = 5) -> List[Dict]:
    """
    Récupère les stationnements vélo les plus proches d'un point géographique.
    
    Args:
        latitude: Latitude du point
        longitude: Longitude du point
        max_distance: Distance maximale en km
        limit: Nombre maximum de résultats
    
    Returns:
        Liste des stationnements vélo les plus proches
    """
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
    
    parkings = get_all_bike_parkings()
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
