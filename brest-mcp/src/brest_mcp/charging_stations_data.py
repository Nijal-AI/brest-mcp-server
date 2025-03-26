"""
Module pour récupérer et traiter les données des bornes de recharge électrique à Brest.
"""
import os
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

# URLs des APIs pour les données de bornes de recharge
CHARGING_STATIONS_URL = os.getenv("CHARGING_STATIONS_URL", 
                                "https://opendata.reseaux-energies.fr/api/records/1.0/search/?dataset=bornes-irve&q=brest&rows=100")

def fetch_charging_stations() -> Optional[Dict]:
    """
    Récupère les données des bornes de recharge électrique pour Brest.
    
    Returns:
        Données des bornes de recharge ou None en cas d'erreur
    """
    try:
        logging.info(f"Fetching charging stations data from {CHARGING_STATIONS_URL}")
        response = requests.get(CHARGING_STATIONS_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching charging stations data: {str(e)}")
        return None

def parse_charging_stations(data: Dict) -> List[Dict]:
    """
    Parse les données des bornes de recharge électrique.
    
    Args:
        data: Données brutes de l'API
    
    Returns:
        Liste des bornes de recharge formatées
    """
    if not data or "records" not in data:
        return []
    
    stations = []
    for record in data.get("records", []):
        fields = record.get("fields", {})
        geo = fields.get("geo_point_2d", [0, 0])
        
        station = {
            "id": record.get("recordid", ""),
            "name": fields.get("n_station", fields.get("nom_station", "")),
            "operator": fields.get("operateur", ""),
            "owner": fields.get("nom_amenageur", ""),
            "address": fields.get("adresse", ""),
            "city": fields.get("commune", "Brest"),
            "postal_code": fields.get("code_postal", ""),
            "access_type": fields.get("condition_acces", ""),
            "payment_method": fields.get("moyen_paiement", ""),
            "coordinates": {
                "latitude": geo[0] if isinstance(geo, list) and len(geo) > 1 else 0,
                "longitude": geo[1] if isinstance(geo, list) and len(geo) > 1 else 0
            },
            "connectors": parse_connectors(fields),
            "last_update": fields.get("date_maj", datetime.now().isoformat())
        }
        stations.append(station)
    
    return stations

def parse_connectors(fields: Dict) -> List[Dict]:
    """
    Parse les informations sur les connecteurs d'une borne.
    
    Args:
        fields: Champs de données d'une borne
    
    Returns:
        Liste des connecteurs formatés
    """
    connectors = []
    
    # Nombre de points de charge
    num_points = fields.get("nbre_pdc", 0)
    
    # Types de connecteurs
    connector_types = fields.get("type_prise", "").split(";") if fields.get("type_prise") else []
    
    # Puissances de charge
    powers = fields.get("puissance_nominale", "").split(";") if fields.get("puissance_nominale") else []
    
    # Formats les connecteurs
    for i in range(min(num_points, len(connector_types))):
        connector_type = connector_types[i] if i < len(connector_types) else "Unknown"
        power = float(powers[i]) if i < len(powers) and powers[i].replace('.', '', 1).isdigit() else 0
        
        connector = {
            "type": connector_type.strip(),
            "power": power,
            "status": "UNKNOWN"  # Par défaut, car les données statiques n'incluent pas le statut
        }
        connectors.append(connector)
    
    return connectors

def get_all_charging_stations() -> List[Dict]:
    """
    Récupère toutes les bornes de recharge électrique.
    
    Returns:
        Liste des bornes de recharge
    """
    data = fetch_charging_stations()
    if not data:
        return []
    
    return parse_charging_stations(data)

def get_charging_station_by_id(station_id: str) -> Optional[Dict]:
    """
    Récupère une borne de recharge par son ID.
    
    Args:
        station_id: ID de la borne de recharge
    
    Returns:
        Informations sur la borne de recharge ou None si elle n'existe pas
    """
    stations = get_all_charging_stations()
    for station in stations:
        if station.get("id") == station_id:
            return station
    return None

def get_charging_stations_by_operator(operator: str) -> List[Dict]:
    """
    Récupère les bornes de recharge par opérateur.
    
    Args:
        operator: Nom de l'opérateur
    
    Returns:
        Liste des bornes de recharge de l'opérateur spécifié
    """
    stations = get_all_charging_stations()
    return [s for s in stations if operator.lower() in s.get("operator", "").lower()]

def get_free_charging_stations() -> List[Dict]:
    """
    Récupère les bornes de recharge gratuites.
    
    Returns:
        Liste des bornes de recharge gratuites
    """
    stations = get_all_charging_stations()
    return [s for s in stations if "gratuit" in s.get("payment_method", "").lower()]

def get_fast_charging_stations(min_power: float = 50.0) -> List[Dict]:
    """
    Récupère les bornes de recharge rapide.
    
    Args:
        min_power: Puissance minimale en kW pour considérer une borne comme rapide
    
    Returns:
        Liste des bornes de recharge rapide
    """
    stations = get_all_charging_stations()
    fast_stations = []
    
    for station in stations:
        connectors = station.get("connectors", [])
        if any(c.get("power", 0) >= min_power for c in connectors):
            station["fast_charging"] = True
            fast_stations.append(station)
    
    return fast_stations

def get_nearest_charging_stations(latitude: float, longitude: float, max_distance: float = 5.0, limit: int = 5) -> List[Dict]:
    """
    Récupère les bornes de recharge les plus proches d'un point géographique.
    
    Args:
        latitude: Latitude du point
        longitude: Longitude du point
        max_distance: Distance maximale en km
        limit: Nombre maximum de résultats
    
    Returns:
        Liste des bornes de recharge les plus proches
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
    
    stations = get_all_charging_stations()
    stations_with_distance = []
    
    for station in stations:
        coords = station.get("coordinates", {})
        s_lat = coords.get("latitude", 0)
        s_lon = coords.get("longitude", 0)
        
        if s_lat and s_lon:
            distance = haversine(longitude, latitude, s_lon, s_lat)
            if distance <= max_distance:
                station["distance"] = distance
                stations_with_distance.append(station)
    
    # Trie par distance et limite le nombre de résultats
    stations_with_distance.sort(key=lambda x: x.get("distance", float("inf")))
    return stations_with_distance[:limit]
