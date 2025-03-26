import os
from dotenv import load_dotenv
import requests
from google.transit import gtfs_realtime_pb2
from mcp.server import FastMCP
from datetime import datetime
from typing import Dict, List, Optional
import json
import logging

# Import des modules pour les différentes sources de données
from brest_mcp.parking_data import get_all_parkings_with_availability, get_parking_by_id, get_nearest_parkings
from brest_mcp.maritime_data import get_next_tides, get_tide_by_date, get_current_tide_status
from brest_mcp.air_quality_data import get_air_quality, get_air_quality_with_recommendations
from brest_mcp.cycling_data import get_all_bike_parkings, get_cycling_routes, get_nearest_bike_parkings
from brest_mcp.charging_stations_data import get_all_charging_stations, get_nearest_charging_stations

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Configuration : URLs des flux GTFS-RT et paramètres depuis .env
VEHICLE_POSITIONS_URL = os.getenv("GTFS_VEHICLE_POSITIONS_URL")
TRIP_UPDATES_URL = os.getenv("GTFS_TRIP_UPDATES_URL")
SERVICE_ALERTS_URL = os.getenv("GTFS_SERVICE_ALERTS_URL")
WEATHER_INFOCLIMAT_URL = os.getenv("WEATHER_INFOCLIMAT_URL", "https://www.infoclimat.fr/public-api/gfs/json?_ll=48.4475,-4.4181&_auth=ARtTRAV7ByVec1FmAnRVfFU9BzIMegIlVCgDYA1oVyoDaFIzVTVcOlE%2FBnsHKFZgBypXNFphU2MCaVAoD31RMAFrUz8FbgdgXjFRNAItVX5VewdmDCwCJVQ1A2QNflc9A2dSKFU3XDZRNwZ6Bz5WZAcrVyhaZFNsAmVQNQ9nUTYBZFM1BWYHbV4uUSwCNFVmVTIHMwwxAj9UNQNkDWRXNwNgUmBVN1w3USAGZwc%2BVmcHPVc2Wm1TbwJkUCgPfVFLARFTKgUmBydeZFF1Ai9VNFU4BzM%3D&_c=38fc48e42684d2b24279d0b02e2d0713")
REFRESH_INTERVAL = int(os.getenv("GTFS_REFRESH_INTERVAL", "30"))
HOST = os.getenv("MCP_HOST", "localhost")
PORT = int(os.getenv("MCP_PORT", "0"))

# Initialiser le serveur MCP avec le nom et les paramètres réseau spécifiés
mcp = FastMCP("BrestCityServer", host=HOST, port=PORT)

# Cache en mémoire pour les données avec timestamps
_cache = {
    "vehicle_positions": {"timestamp": 0, "data": None, "last_update": None},
    "trip_updates": {"timestamp": 0, "data": None, "last_update": None},
    "service_alerts": {"timestamp": 0, "data": None, "last_update": None},
    "weather_infoclimat": {"timestamp": 0, "data": None, "last_update": None},
    "parkings": {"timestamp": 0, "data": None, "last_update": None},
    "tides": {"timestamp": 0, "data": None, "last_update": None},
    "air_quality": {"timestamp": 0, "data": None, "last_update": None},
    "bike_parkings": {"timestamp": 0, "data": None, "last_update": None},
    "cycling_routes": {"timestamp": 0, "data": None, "last_update": None},
    "charging_stations": {"timestamp": 0, "data": None, "last_update": None}
}

def _fetch_feed(feed_type: str, is_json: bool = False, is_static: bool = False) -> Optional[any]:
    """Récupère un flux de données et le met en cache."""
    now = datetime.now().timestamp()
    cache = _cache[feed_type]
    
    # Si les données sont assez récentes, utiliser le cache
    if now - cache["timestamp"] < REFRESH_INTERVAL and cache["data"]:
        return cache["data"]
    
    # Sinon, récupérer les nouvelles données
    try:
        url = {
            "vehicle_positions": VEHICLE_POSITIONS_URL,
            "trip_updates": TRIP_UPDATES_URL,
            "service_alerts": SERVICE_ALERTS_URL,
            "weather_infoclimat": WEATHER_INFOCLIMAT_URL
        }.get(feed_type)
        
        if not url:
            # Pour les autres types de données, utiliser les fonctions spécifiques
            if feed_type == "parkings":
                data = get_all_parkings_with_availability()
            elif feed_type == "tides":
                data = get_next_tides(8)  # 8 prochaines marées
            elif feed_type == "air_quality":
                data = get_air_quality().get("data", {})
            elif feed_type == "bike_parkings":
                data = get_all_bike_parkings()
            elif feed_type == "cycling_routes":
                data = get_cycling_routes()
            elif feed_type == "charging_stations":
                data = get_all_charging_stations()
            else:
                return None
        else:
            logging.info(f"Fetching {feed_type} from {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            if is_json:
                data = response.json()
            elif is_static:
                data = response.content
            else:
                feed = gtfs_realtime_pb2.FeedMessage()
                feed.ParseFromString(response.content)
                data = feed
        
        # Mettre à jour le cache
        cache["data"] = data
        cache["timestamp"] = now
        cache["last_update"] = now
        logging.info(f"Successfully fetched {feed_type}")
        
        return data
    except Exception as e:
        logging.error(f"Error fetching {feed_type}: {str(e)}")
        return None

# Configuration des URLs GTFS-RT pour différents réseaux bretons
NETWORK_URLS = {
    "bibus": {
        "vehicle_positions": "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-vehicle-position",
        "trip_updates": "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-trip-update",
        "service_alerts": "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-alerts"
    },
    "star": {  # Rennes
        "vehicle_positions": "https://proxy.transport.data.gouv.fr/resource/star-rennes-gtfs-rt-vehicle-position",
        "trip_updates": "https://proxy.transport.data.gouv.fr/resource/star-rennes-gtfs-rt-trip-update",
        "service_alerts": "https://proxy.transport.data.gouv.fr/resource/star-rennes-gtfs-rt-alerts"
    },
    "tub": {  # Saint-Brieuc
        "vehicle_positions": "https://proxy.transport.data.gouv.fr/resource/tub-saint-brieuc-gtfs-rt-vehicle-position",
        "trip_updates": "https://proxy.transport.data.gouv.fr/resource/tub-saint-brieuc-gtfs-rt-trip-update",
        "service_alerts": "https://proxy.transport.data.gouv.fr/resource/tub-saint-brieuc-gtfs-rt-alerts"
    }
}

# Mise à jour des variables d'environnement avec le réseau par défaut (Bibus)
VEHICLE_POSITIONS_URL = os.getenv("GTFS_VEHICLE_POSITIONS_URL", NETWORK_URLS["bibus"]["vehicle_positions"])
TRIP_UPDATES_URL = os.getenv("GTFS_TRIP_UPDATES_URL", NETWORK_URLS["bibus"]["trip_updates"])
SERVICE_ALERTS_URL = os.getenv("GTFS_SERVICE_ALERTS_URL", NETWORK_URLS["bibus"]["service_alerts"])

# Fonctions existantes pour les données GTFS-RT
# [Insérer ici toutes les fonctions existantes pour le traitement des données GTFS-RT]
# _get_vehicle_positions_data, _get_trip_updates_data, _get_service_alerts_data, etc.

# Nouvelles fonctions pour les données de parkings
@mcp.tool("get_parkings")
def get_parkings():
    """Récupère tous les parkings avec leur disponibilité en temps réel."""
    data = _fetch_feed("parkings")
    return {
        "status": "success",
        "data": data or [],
        "lastUpdate": _cache["parkings"]["last_update"]
    }

@mcp.tool()
def get_parking(parking_id: str):
    """Récupère les informations d'un parking spécifique."""
    return get_parking_by_id(parking_id)

@mcp.tool()
def find_nearest_parkings(latitude: float, longitude: float, max_distance: float = 1.0, limit: int = 5):
    """Trouve les parkings les plus proches d'un point géographique."""
    return get_nearest_parkings(latitude, longitude, max_distance, limit)

# Nouvelles fonctions pour les données maritimes
@mcp.tool("get_tides")
def get_tides():
    """Récupère les prochaines marées pour Brest."""
    data = _fetch_feed("tides")
    return {
        "status": "success",
        "data": data or [],
        "lastUpdate": _cache["tides"]["last_update"]
    }

@mcp.tool()
def get_tide_status():
    """Récupère le statut actuel de la marée (montante/descendante)."""
    return get_current_tide_status()

@mcp.tool()
def get_tides_for_date(date: str):
    """Récupère les marées pour une date spécifique."""
    return get_tide_by_date(date)

# Nouvelles fonctions pour les données de qualité de l'air
@mcp.tool("get_air_quality")
def get_air_quality_data():
    """Récupère les données de qualité de l'air pour Brest."""
    return get_air_quality_with_recommendations()

# Nouvelles fonctions pour les données de vélos
@mcp.tool("get_bike_parkings")
def get_bike_parkings_data():
    """Récupère tous les stationnements vélo."""
    data = _fetch_feed("bike_parkings")
    return {
        "status": "success",
        "data": data or [],
        "lastUpdate": _cache["bike_parkings"]["last_update"]
    }

@mcp.tool("get_cycling_routes")
def get_cycling_routes_data():
    """Récupère toutes les pistes cyclables."""
    data = _fetch_feed("cycling_routes")
    return {
        "status": "success",
        "data": data or [],
        "lastUpdate": _cache["cycling_routes"]["last_update"]
    }

@mcp.tool()
def find_nearest_bike_parkings(latitude: float, longitude: float, max_distance: float = 1.0, limit: int = 5):
    """Trouve les stationnements vélo les plus proches d'un point géographique."""
    return get_nearest_bike_parkings(latitude, longitude, max_distance, limit)

# Nouvelles fonctions pour les données de bornes de recharge
@mcp.tool("get_charging_stations")
def get_charging_stations_data():
    """Récupère toutes les bornes de recharge électrique."""
    data = _fetch_feed("charging_stations")
    return {
        "status": "success",
        "data": data or [],
        "lastUpdate": _cache["charging_stations"]["last_update"]
    }

@mcp.tool()
def find_nearest_charging_stations(latitude: float, longitude: float, max_distance: float = 5.0, limit: int = 5):
    """Trouve les bornes de recharge les plus proches d'un point géographique."""
    return get_nearest_charging_stations(latitude, longitude, max_distance, limit)

# Ressources MCP pour les nouvelles données
@mcp.resource("brest://parkings")
def parkings_resource():
    """Ressource pour tous les parkings."""
    return get_parkings()

@mcp.resource("brest://parking/{parking_id}")
def parking_resource(parking_id: str):
    """Ressource pour un parking spécifique."""
    parking = get_parking(parking_id)
    return {
        "status": "success" if parking else "error",
        "data": parking or {},
        "message": None if parking else f"Parking {parking_id} non trouvé"
    }

@mcp.resource("brest://tides")
def tides_resource():
    """Ressource pour les marées."""
    return get_tides()

@mcp.resource("brest://tides/current")
def current_tide_resource():
    """Ressource pour le statut actuel de la marée."""
    return get_tide_status()

@mcp.resource("brest://tides/{date}")
def tides_by_date_resource(date: str):
    """Ressource pour les marées d'une date spécifique."""
    tides = get_tides_for_date(date)
    return {
        "status": "success",
        "data": tides,
        "date": date
    }

@mcp.resource("brest://air-quality")
def air_quality_resource():
    """Ressource pour la qualité de l'air."""
    return get_air_quality_data()

@mcp.resource("brest://bike-parkings")
def bike_parkings_resource():
    """Ressource pour les stationnements vélo."""
    return get_bike_parkings_data()

@mcp.resource("brest://cycling-routes")
def cycling_routes_resource():
    """Ressource pour les pistes cyclables."""
    return get_cycling_routes_data()

@mcp.resource("brest://charging-stations")
def charging_stations_resource():
    """Ressource pour les bornes de recharge électrique."""
    return get_charging_stations_data()

@mcp.resource("brest://nearest/{type}/{latitude}/{longitude}")
def nearest_resource(type: str, latitude: float, longitude: float):
    """
    Ressource pour trouver les équipements les plus proches d'un point géographique.
    
    Args:
        type: Type d'équipement (parking, bike-parking, charging-station)
        latitude: Latitude du point
        longitude: Longitude du point
    """
    max_distance = 1.0  # Valeur par défaut
    limit = 5  # Valeur par défaut
    
    if type == "parking":
        data = find_nearest_parkings(latitude, longitude, max_distance, limit)
    elif type == "bike-parking":
        data = find_nearest_bike_parkings(latitude, longitude, max_distance, limit)
    elif type == "charging-station":
        data = find_nearest_charging_stations(latitude, longitude, max_distance, limit)
    else:
        return {
            "status": "error",
            "message": f"Type {type} non reconnu. Types disponibles : parking, bike-parking, charging-station"
        }
    
    return {
        "status": "success",
        "type": type,
        "data": data,
        "count": len(data),
        "coordinates": {
            "latitude": latitude,
            "longitude": longitude
        },
        "max_distance": max_distance,
        "timestamp": datetime.now().isoformat()
    }

@mcp.resource("brest://city-data")
def city_data_resource():
    """
    Ressource regroupant les principales données de la ville.
    Fournit un aperçu global des différentes sources de données disponibles.
    """
    # Récupère un échantillon de chaque type de données
    try:
        weather = _fetch_feed("weather_infoclimat", is_json=True)
        weather_data = _parse_weather_infoclimat(weather) if weather else {}
        current_weather = next(iter(weather_data.values())) if weather_data else {}
        
        vehicles = _get_vehicle_positions_data()
        vehicle_count = len(vehicles)
        
        alerts = _get_service_alerts_data()
        alert_count = len(alerts)
        
        parkings = _fetch_feed("parkings")
        parking_count = len(parkings) if parkings else 0
        
        tides = get_current_tide_status()
        
        air_quality = get_air_quality().get("data", {})
        
        charging_stations = _fetch_feed("charging_stations")
        charging_count = len(charging_stations) if charging_stations else 0
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "weather": {
                    "temperature": current_weather.get("temperature_2m"),
                    "wind_speed": current_weather.get("wind_speed"),
                    "humidity": current_weather.get("humidity"),
                    "precipitation": current_weather.get("precipitation")
                },
                "transport": {
                    "active_vehicles": vehicle_count,
                    "alerts": alert_count
                },
                "parkings": {
                    "count": parking_count,
                    "available": sum(p.get("availability", {}).get("available_spaces", 0) for p in parkings) if parkings else 0
                },
                "maritime": {
                    "tide_status": tides.get("tide_direction"),
                    "water_level": tides.get("current_level")
                },
                "environment": {
                    "air_quality_index": air_quality.get("aqi"),
                    "air_quality_level": air_quality.get("level")
                },
                "mobility": {
                    "charging_stations": charging_count
                }
            }
        }
    except Exception as e:
        logging.error(f"Error generating city data: {str(e)}")
        return {
            "status": "error",
            "message": "Error generating city data"
        }

if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "tcp":
        logging.info("Transport 'tcp' non supporté, utilisation de 'sse' à la place.")
        transport = "sse"
    logging.info(f"Starting Brest MCP Server with transport: {transport} on {HOST}:{PORT}")
    mcp.run(transport=transport)