import os
from dotenv import load_dotenv
import requests
from google.transit import gtfs_realtime_pb2
from mcp.server import FastMCP
from datetime import datetime
from typing import Dict, List, Optional
import json
import logging

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
mcp = FastMCP("TransitServer", host=HOST, port=PORT)

# Cache en mémoire pour les données GTFS-RT avec timestamps
_cache = {
    "vehicle_positions": {"timestamp": 0, "data": None, "last_update": None},
    "trip_updates": {"timestamp": 0, "data": None, "last_update": None},
    "service_alerts": {"timestamp": 0, "data": None, "last_update": None},
    "weather_infoclimat": {"timestamp": 0, "data": None, "last_update": None}
}

def _fetch_feed(feed_type: str, is_json: bool = False, is_static: bool = False) -> Optional[any]:
    """Récupère un flux GTFS-RT et le met en cache."""
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
        }[feed_type]
        
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

def _get_vehicle_positions_data() -> List[Dict]:
    """Récupère les positions de tous les véhicules."""
    feed = _fetch_feed("vehicle_positions")
    if feed:
        return _parse_vehicle_positions(feed)
    return []

def _get_trip_updates_data() -> List[Dict]:
    """Récupère les mises à jour de tous les trajets."""
    feed = _fetch_feed("trip_updates")
    if feed:
        return _parse_trip_updates(feed)
    return []

def _get_service_alerts_data() -> List[Dict]:
    """Récupère les alertes de service actives."""
    feed = _fetch_feed("service_alerts")
    if feed:
        return _parse_service_alerts(feed)
    return []

def _parse_vehicle_positions(feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
    """Transforme un FeedMessage de positions véhicules en une liste de dictionnaires."""
    data = []
    for entity in feed.entity:
        if not entity.HasField('vehicle'):
            continue
        vp = entity.vehicle
        vehicle_info = {}
        vehicle_info["vehicle_id"] = entity.id or (vp.vehicle.id if vp.vehicle.HasField('id') else vp.vehicle.label)
        if vp.position:
            vehicle_info["latitude"] = vp.position.latitude
            vehicle_info["longitude"] = vp.position.longitude
            if vp.position.HasField('bearing'):
                vehicle_info["bearing"] = vp.position.bearing
            if vp.position.HasField('speed'):
                vehicle_info["speed"] = vp.position.speed
        if vp.trip:
            vehicle_info["trip_id"] = vp.trip.trip_id
            vehicle_info["route_id"] = vp.trip.route_id
            vehicle_info["start_time"] = vp.trip.start_time
            vehicle_info["start_date"] = vp.trip.start_date
        if vp.HasField('timestamp'):
            vehicle_info["timestamp"] = vp.timestamp
        data.append(vehicle_info)
    return data

def _parse_trip_updates(feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
    """Transforme un FeedMessage de mises à jour de trajets en une liste de dictionnaires."""
    data = []
    for entity in feed.entity:
        if not entity.HasField('trip_update'):
            continue
        tu = entity.trip_update
        trip_info = {}
        trip_info["trip_id"] = tu.trip.trip_id
        trip_info["route_id"] = tu.trip.route_id
        trip_info["start_time"] = tu.trip.start_time
        trip_info["start_date"] = tu.trip.start_date
        if tu.vehicle and tu.vehicle.HasField('id'):
            trip_info["vehicle_id"] = tu.vehicle.id
        updates = []
        for stu in tu.stop_time_update:
            update_info = {}
            if stu.stop_id:
                update_info["stop_id"] = stu.stop_id
            if stu.HasField('arrival') and stu.arrival.HasField('delay'):
                update_info["arrival_delay"] = stu.arrival.delay
            if stu.HasField('departure') and stu.departure.HasField('delay'):
                update_info["departure_delay"] = stu.departure.delay
            if stu.HasField('arrival') and stu.arrival.HasField('time'):
                update_info["arrival_time"] = stu.arrival.time
            if stu.HasField('departure') and stu.departure.HasField('time'):
                update_info["departure_time"] = stu.departure.time
            if stu.HasField('schedule_relationship'):
                update_info["schedule_relationship"] = str(stu.schedule_relationship)
            if update_info:
                updates.append(update_info)
        if updates:
            trip_info["stop_time_updates"] = updates
        data.append(trip_info)
    return data

def _parse_service_alerts(feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
    """Transforme un FeedMessage d'alertes de service en une liste de dictionnaires."""
    data = []
    cause_map = {
        1: "UNKNOWN_CAUSE", 2: "OTHER_CAUSE", 3: "TECHNICAL_PROBLEM", 4: "STRIKE",
        5: "DEMONSTRATION", 6: "ACCIDENT", 7: "HOLIDAY", 8: "WEATHER",
        9: "MAINTENANCE", 10: "CONSTRUCTION", 11: "POLICE_ACTIVITY", 12: "MEDICAL_EMERGENCY"
    }
    effect_map = {
        1: "NO_SERVICE", 2: "REDUCED_SERVICE", 3: "SIGNIFICANT_DELAYS", 4: "DETOUR",
        5: "ADDITIONAL_SERVICE", 6: "MODIFIED_SERVICE", 7: "OTHER_EFFECT",
        8: "UNKNOWN_EFFECT", 9: "STOP_MOVED"
    }
    for entity in feed.entity:
        if not entity.HasField('alert'):
            continue
        alert = entity.alert
        alert_info = {}
        alert_info["alert_id"] = entity.id
        if alert.HasField('cause') and alert.cause in cause_map:
            alert_info["cause"] = cause_map[alert.cause]
        if alert.HasField('effect') and alert.effect in effect_map:
            alert_info["effect"] = effect_map[alert.effect]
        periods = []
        for period in alert.active_period:
            period_info = {}
            if period.HasField('start'):
                period_info["start"] = period.start
            if period.HasField('end'):
                period_info["end"] = period.end
            if period_info:
                periods.append(period_info)
        if periods:
            alert_info["active_periods"] = periods
        routes = set()
        stops = set()
        for ie in alert.informed_entity:
            if ie.HasField('route_id'):
                routes.add(ie.route_id)
            if ie.HasField('stop_id'):
                stops.add(ie.stop_id)
        if routes:
            alert_info["routes"] = list(routes)
        if stops:
            alert_info["stops"] = list(stops)
        description = None
        if alert.description_text and alert.description_text.translation:
            for translation in alert.description_text.translation:
                if translation.language and translation.language.startswith("en"):
                    description = translation.text
                    break
            if description is None:
                description = alert.description_text.translation[0].text
        if description:
            alert_info["description"] = description
        header = None
        if alert.header_text and alert.header_text.translation:
            for translation in alert.header_text.translation:
                if translation.language and translation.language.startswith("en"):
                    header = translation.text
                    break
            if header is None:
                header = alert.header_text.translation[0].text
        if header:
            alert_info["header"] = header
        data.append(alert_info)
    return data

def _parse_weather_infoclimat(data: Dict) -> Dict:
    """Transforme les données Infoclimat en un dictionnaire structuré."""
    forecasts = {}
    for timestamp, values in data.items():
        if timestamp.startswith("20"):  # Filtrer les timestamps valides
            forecasts[timestamp] = {
                "temperature_2m": values.get("temperature", {}).get("2m"),
                "wind_speed": values.get("vent_moyen", {}).get("10m"),
                "wind_gusts": values.get("vent_rafales", {}).get("10m"),
                "wind_direction": values.get("vent_direction", {}).get("10m"),
                "precipitation": values.get("pluie"),
                "humidity": values.get("humidite", {}).get("2m"),
                "pressure": values.get("pression", {}).get("niveau_de_la_mer")
            }
    return forecasts

@mcp.tool("get_vehicles")
def get_vehicle_positions():
    """Charge et retourne les positions de tous les véhicules en temps réel."""
    return {
        "status": "success",
        "data": _get_vehicle_positions_data(),
        "lastUpdate": _cache["vehicle_positions"]["last_update"]
    }

@mcp.tool("get_trip_updates")
def get_trip_updates():
    """Charge et retourne toutes les mises à jour des trajets en temps réel."""
    return {
        "status": "success",
        "data": _get_trip_updates_data(),
        "lastUpdate": _cache["trip_updates"]["last_update"]
    }

@mcp.tool("get_alerts")
def get_service_alerts():
    """Charge et retourne toutes les alertes de service actives en temps réel."""
    return {
        "status": "success",
        "data": _get_service_alerts_data(),
        "lastUpdate": _cache["service_alerts"]["last_update"]
    }

@mcp.tool("get_weather_forecast")
def get_weather_forecast():
    """Récupère les prévisions météo pour Brest."""
    data = _fetch_feed("weather_infoclimat", is_json=True)
    return {
        "status": "success", 
        "data": _parse_weather_infoclimat(data) if data else {}, 
        "lastUpdate": _cache["weather_infoclimat"]["last_update"]
    }

@mcp.tool()
def get_vehicle(vehicle_id: str):
    """Retourne les informations du véhicule spécifié par son identifiant."""
    vehicles = _get_vehicle_positions_data()
    for v in vehicles:
        if str(v.get("vehicle_id")) == str(vehicle_id):
            return v
    return None

@mcp.tool()
def get_trip_update(trip_id: str):
    """Retourne les informations de mise à jour du trajet spécifié."""
    trips = _get_trip_updates_data()
    for t in trips:
        if t.get("trip_id") == trip_id:
            return t
    return None

@mcp.tool()
def get_alert(alert_id: str):
    """Retourne les détails de l'alerte de service spécifiée."""
    alerts = _get_service_alerts_data()
    for a in alerts:
        if a.get("alert_id") == alert_id:
            return a
    return None

@mcp.tool()
def get_weather_by_timestamp(timestamp: str):
    """Récupère les prévisions météo pour un timestamp spécifique (format ISO)."""
    data = _fetch_feed("weather_infoclimat", is_json=True)
    forecasts = _parse_weather_infoclimat(data) if data else {}
    return forecasts.get(timestamp, None)

@mcp.tool()
def count_vehicles():
    """Retourne le nombre de véhicules actuellement suivis."""
    vehicles = _get_vehicle_positions_data()
    return len(vehicles)

@mcp.tool()
def count_alerts():
    """Retourne le nombre d'alertes de service actives."""
    alerts = _get_service_alerts_data()
    return len(alerts)

@mcp.tool()
def find_trips_by_route(route_id: str):
    """Liste les identifiants des trajets en cours pour la ligne donnée."""
    trips = _get_trip_updates_data()
    return [t["trip_id"] for t in trips if t.get("route_id") == route_id]

@mcp.tool()
def find_vehicles_by_route(route_id: str) -> List[Dict]:
    """Trouve tous les véhicules sur une ligne spécifique."""
    vehicles = []
    feed = _fetch_feed("vehicle_positions")
    if not feed:
        return vehicles
        
    for entity in feed.entity:
        if entity.HasField('vehicle'):
            vp = entity.vehicle
            if vp.HasField('trip') and vp.trip.HasField('route_id') and vp.trip.route_id == route_id:
                vehicle_info = {
                    "vehicle_id": vp.vehicle.id if vp.vehicle.HasField('id') else vp.vehicle.label,
                    "position": {
                        "latitude": vp.position.latitude,
                        "longitude": vp.position.longitude,
                        "bearing": vp.position.bearing if vp.position.HasField('bearing') else None,
                        "speed": vp.position.speed if vp.position.HasField('speed') else None
                    },
                    "trip_id": vp.trip.trip_id,
                    "current_status": vp.current_status if vp.HasField('current_status') else None,
                    "timestamp": vp.timestamp if vp.HasField('timestamp') else None
                }
                vehicles.append(vehicle_info)
    return vehicles

@mcp.tool()
def find_alerts_by_route(route_id: str) -> List[Dict]:
    """Trouve toutes les alertes pour une ligne spécifique."""
    alerts = []
    feed = _fetch_feed("service_alerts")
    if not feed:
        return alerts
        
    for entity in feed.entity:
        if entity.HasField('alert'):
            alert = entity.alert
            # Vérifie si l'alerte concerne cette ligne
            for informed_entity in alert.informed_entity:
                if informed_entity.HasField('route_id') and informed_entity.route_id == route_id:
                    alert_info = {
                        "id": entity.id,
                        "effect": alert.effect,
                        "header": alert.header_text.translation[0].text if alert.header_text.translation else None,
                        "description": alert.description_text.translation[0].text if alert.description_text.translation else None,
                        "start": alert.active_period[0].start if alert.active_period else None,
                        "end": alert.active_period[0].end if alert.active_period else None
                    }
                    alerts.append(alert_info)
                    break
    return alerts

@mcp.resource("gtfs://vehicles")
def vehicles_resource() -> Dict:
    """Liste tous les véhicules actifs."""
    return get_vehicle_positions()

@mcp.resource("gtfs://vehicle/{vehicle_id}")
def vehicle_resource(vehicle_id: str) -> Dict:
    """Détails d'un véhicule spécifique."""
    return get_vehicle(vehicle_id)

@mcp.resource("gtfs://route/{route_id}")
def route_resource(route_id: str) -> Dict:
    """État d'une ligne spécifique."""
    vehicles = find_vehicles_by_route(route_id)
    alerts = find_alerts_by_route(route_id)
    
    return {
        "status": "success",
        "data": {
            "route_id": route_id,
            "vehicles": vehicles,
            "alerts": alerts,
            "statistics": {
                "vehicle_count": len(vehicles),
                "alert_count": len(alerts)
            },
            "timestamp": datetime.now().isoformat()
        }
    }

@mcp.resource("gtfs://network/stats")
def network_stats_resource() -> Dict:
    """Statistiques du réseau."""
    return {
        "status": "success",
        "data": _get_network_statistics()
    }

@mcp.resource("gtfs://weather")
def weather_resource():
    """Ressource pour les prévisions météo."""
    return get_weather_forecast()

@mcp.resource("gtfs://weather/{timestamp}")
def weather_by_timestamp_resource(timestamp: str):
    """Ressource pour les prévisions météo à un moment spécifique."""
    forecast = get_weather_by_timestamp(timestamp)
    return {
        "status": "success" if forecast else "error",
        "data": forecast or {},
        "timestamp": timestamp,
        "message": None if forecast else "Aucune prévision disponible pour ce timestamp"
    }

def _get_network_statistics() -> Dict:
    """Calcule des statistiques sur l'état du réseau."""
    vehicles = _get_vehicle_positions_data()
    trips = _get_trip_updates_data()
    
    return {
        "totalVehicles": len(vehicles),
        "vehiclesByStatus": _count_vehicles_by_status(vehicles),
        "averageDelay": _calculate_average_delay(trips),
        "routesWithAlerts": len(set(alert.get("route_id") for alert in _get_service_alerts_data())),
        "onTimePerformance": _calculate_on_time_performance(trips)
    }

def _count_vehicles_by_status(vehicles: List[Dict]) -> Dict:
    """Compte les véhicules par statut."""
    status_count = {"IN_TRANSIT": 0, "STOPPED": 0, "UNKNOWN": 0}
    for vehicle in vehicles:
        current_status = vehicle.get("currentStatus", "UNKNOWN")
        status_count[current_status] = status_count.get(current_status, 0) + 1
    return status_count

def _calculate_average_delay(trips: List[Dict]) -> float:
    """Calcule le retard moyen sur l'ensemble du réseau."""
    delays = [
        stop.get("arrival_delay", 0)
        for trip in trips
        for stop in trip.get("stop_time_updates", [])
    ]
    return sum(delays) / len(delays) if delays else 0

def _calculate_on_time_performance(trips: List[Dict], threshold: int = 180) -> float:
    """Calcule le pourcentage de véhicules à l'heure (retard < seuil)."""
    total = 0
    on_time = 0
    
    for trip in trips:
        for stop in trip.get("stop_time_updates", []):
            total += 1
            if abs(stop.get("arrival_delay", 0)) < threshold:
                on_time += 1
    
    return (on_time / total * 100) if total > 0 else 100

def _get_trip_details(trip_id: str) -> Optional[Dict]:
    """Récupère les détails d'un trajet spécifique."""
    if not trip_id:
        return None
        
    trips = _get_trip_updates_data()
    for trip in trips:
        if trip.get("trip_id") == trip_id:
            return trip
    return None

def _get_vehicle_alerts(vehicle_id: str) -> List[Dict]:
    """Récupère les alertes affectant un véhicule spécifique."""
    alerts = _get_service_alerts_data()
    return [
        alert for alert in alerts
        if vehicle_id in [ie.vehicle_id for ie in alert.informed_entity if ie.HasField('vehicle_id')]
    ]

def _get_route_delays(route_id: str) -> Dict:
    """Calcule les statistiques de retard pour une ligne spécifique."""
    trips = _get_trip_updates_data()
    route_trips = [
        trip for trip in trips
        if trip.get("route_id") == route_id
    ]
    
    delays = []
    for trip in route_trips:
        for stop in trip.get("stop_time_updates", []):
            delay = stop.get("arrival_delay", 0)
            delays.append(delay)
    
    return {
        "averageDelay": sum(delays) / len(delays) if delays else 0,
        "maxDelay": max(delays) if delays else 0,
        "minDelay": min(delays) if delays else 0,
        "delayedStops": len([d for d in delays if d > 180])
    }

def _get_network_feed(network: str, feed_type: str) -> Optional[gtfs_realtime_pb2.FeedMessage]:
    """Récupère un flux GTFS-RT pour un réseau spécifique."""
    if network not in NETWORK_URLS:
        return None
        
    try:
        url = NETWORK_URLS[network][feed_type]
        logging.info(f"Fetching {feed_type} from {network} at {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        logging.info(f"Successfully fetched {network} {feed_type} with {len(feed.entity)} entities")
        return feed
    except Exception as e:
        logging.error(f"Error fetching {network} {feed_type}: {str(e)}")
        return None

@mcp.resource("gtfs://network/{network}/vehicles")
def network_vehicles_resource(network: str) -> Dict:
    """Liste tous les véhicules d'un réseau spécifique."""
    feed = _get_network_feed(network, "vehicle_positions")
    if not feed:
        return {"status": "error", "message": f"Réseau {network} non trouvé ou données indisponibles"}
    
    vehicles = []
    for entity in feed.entity:
        if entity.HasField('vehicle'):
            vp = entity.vehicle
            vehicle_info = {
                "vehicle_id": vp.vehicle.id if vp.vehicle.HasField('id') else vp.vehicle.label,
                "position": {
                    "latitude": vp.position.latitude,
                    "longitude": vp.position.longitude,
                    "bearing": vp.position.bearing if vp.position.HasField('bearing') else None,
                    "speed": vp.position.speed if vp.position.HasField('speed') else None
                },
                "trip_id": vp.trip.trip_id if vp.HasField('trip') else None,
                "route_id": vp.trip.route_id if vp.HasField('trip') else None,
                "current_status": vp.current_status if vp.HasField('current_status') else None,
                "timestamp": vp.timestamp if vp.HasField('timestamp') else None
            }
            vehicles.append(vehicle_info)
    
    return {
        "status": "success",
        "network": network,
        "data": vehicles,
        "count": len(vehicles),
        "timestamp": datetime.now().isoformat()
    }

@mcp.resource("gtfs://networks")
def available_networks_resource() -> Dict:
    """Liste tous les réseaux disponibles."""
    networks = []
    for network, urls in NETWORK_URLS.items():
        networks.append({
            "id": network,
            "name": {
                "bibus": "Bibus (Brest)",
                "star": "STAR (Rennes)",
                "tub": "TUB (Saint-Brieuc)"
            }.get(network, network),
            "urls": urls
        })
    
    return {
        "status": "success",
        "data": networks,
        "count": len(networks)
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