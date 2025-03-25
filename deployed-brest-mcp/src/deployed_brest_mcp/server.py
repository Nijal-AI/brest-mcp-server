import os
from dotenv import load_dotenv
import requests
from google.transit import gtfs_realtime_pb2
from mcp.server import FastMCP
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time
import sys
import logging
from jose import JWTError, jwt

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Configuration : URLs des flux GTFS-RT et paramètres depuis .env
VEHICLE_POSITIONS_URL = os.getenv("GTFS_VEHICLE_POSITIONS_URL")
TRIP_UPDATES_URL = os.getenv("GTFS_TRIP_UPDATES_URL")
SERVICE_ALERTS_URL = os.getenv("GTFS_SERVICE_ALERTS_URL")
REFRESH_INTERVAL = int(os.getenv("GTFS_REFRESH_INTERVAL", "30"))
HOST = os.getenv("MCP_HOST", "localhost")
PORT = int(os.getenv("MCP_PORT", "3001"))
NETWORK = os.getenv("NETWORK", "bibus")

# Configuration OAuth GitHub
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Configuration du logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Initialiser le serveur MCP (FastMCP est le serveur low level intégré)
mcp = FastMCP(
    "Brest-MCP-Server",
    host=HOST,
    port=PORT,
    sse_path="/sse",
    message_path="/messages/",
)

# Cache en mémoire pour les données GTFS-RT avec timestamps
_cache = {
    "vehicle_positions": {"timestamp": 0, "data": None, "last_update": None},
    "trip_updates": {"timestamp": 0, "data": None, "last_update": None},
    "service_alerts": {"timestamp": 0, "data": None, "last_update": None},
    "open_agenda": {"timestamp": 0, "data": None, "last_update": None},
    "weather_infoclimat": {"timestamp": 0, "data": None, "last_update": None},
    "gtfs_static": {"timestamp": 0, "data": None, "last_update": None}
}

# Configuration des URLs GTFS-RT pour différents réseaux bretons
NETWORK_URLS = {
    "bibus": {
        "vehicle_positions": os.getenv("GTFS_VEHICLE_POSITIONS_URL", 
            "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-vehicle-position"),
        "trip_updates": os.getenv("GTFS_TRIP_UPDATES_URL", 
            "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-trip-update"),
        "service_alerts": os.getenv("GTFS_SERVICE_ALERTS_URL", 
            "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-alerts"),
        "gtfs_static": os.getenv("GTFS_STATIC_URL", 
            "https://s3.eu-west-1.amazonaws.com/files.orchestra.ratpdev.com/networks/bibus/exports/medias.zip"),
        "open_agenda": os.getenv("OPEN_AGENDA_URL", 
            "https://api.openagenda.com/v2/events?search=brest&limit=10&key=cf7141c803f746f0abec6bb1667d55e2"),
        "weather_infoclimat": os.getenv("WEATHER_INFOCLIMAT_URL", 
            "https://www.infoclimat.fr/public-api/gfs/json?_ll=48.4475,-4.4181&_auth=ARtTRAV7ByVec1FmAnRVfFU9BzIMegIlVCgDYA1oVyoDaFIzVTVcOlE%2FBnsHKFZgBypXNFphU2MCaVAoD31RMAFrUz8FbgdgXjFRNAItVX5VewdmDCwCJVQ1A2QNflc9A2dSKFU3XDZRNwZ6Bz5WZAcrVyhaZFNsAmVQNQ9nUTYBZFM1BWYHbV4uUSwCNFVmVTIHMwwxAj9UNQNkDWRXNwNgUmBVN1w3USAGZwc%2BVmcHPVc2Wm1TbwJkUCgPfVFLARFTKgUmBydeZFF1Ai9VNFU4BzM%3D&_c=38fc48e42684d2b24279d0b02e2d0713")
    },
    "star": {
        "vehicle_positions": "https://proxy.transport.data.gouv.fr/resource/star-rennes-gtfs-rt-vehicle-position",
        "trip_updates": "https://proxy.transport.data.gouv.fr/resource/star-rennes-gtfs-rt-trip-update",
        "service_alerts": "https://proxy.transport.data.gouv.fr/resource/star-rennes-gtfs-rt-alerts"
    },
    "tub": {
        "vehicle_positions": "https://proxy.transport.data.gouv.fr/resource/tub-saint-brieuc-gtfs-rt-vehicle-position",
        "trip_updates": "https://proxy.transport.data.gouv.fr/resource/tub-saint-brieuc-gtfs-rt-trip-update",
        "service_alerts": "https://proxy.transport.data.gouv.fr/resource/tub-saint-brieuc-gtfs-rt-alerts"
    }
}

VEHICLE_POSITIONS_URL = os.getenv("GTFS_VEHICLE_POSITIONS_URL", NETWORK_URLS[NETWORK]["vehicle_positions"])
TRIP_UPDATES_URL = os.getenv("GTFS_TRIP_UPDATES_URL", NETWORK_URLS[NETWORK]["trip_updates"])
SERVICE_ALERTS_URL = os.getenv("GTFS_SERVICE_ALERTS_URL", NETWORK_URLS[NETWORK]["service_alerts"])

# Fonctions OAuth
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[str]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

# Outils OAuth exposés via MCP (pas besoin de token initial pour ces outils)
@mcp.tool("get_login_url")
def get_login_url():
    redirect_uri = f"http://{HOST}:{PORT}/tools/auth_callback"
    return {
        "status": "success",
        "url": f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={redirect_uri}&scope=user"
    }

@mcp.tool("auth_callback")
def auth_callback(code: str):
    redirect_uri = f"http://{HOST}:{PORT}/tools/auth_callback"
    token_url = "https://github.com/login/oauth/access_token"
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}
    response = requests.post(token_url, data=payload, headers=headers)
    response_data = response.json()
    if "access_token" not in response_data:
        return {"status": "error", "message": "Erreur lors de l'obtention du token GitHub"}
    github_token = response_data["access_token"]
    user_response = requests.get("https://api.github.com/user",
                                 headers={"Authorization": f"token {github_token}"})
    user_data = user_response.json()
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user_data["login"]},
                                       expires_delta=access_token_expires)
    return {"status": "success", "access_token": access_token, "token_type": "bearer"}

# --- Intégration avec FastAPI ---
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
import uvicorn

app = FastAPI()

@app.get("/tools/auth_callback")
async def auth_callback_get(request: Request):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"status": "error", "message": "Missing code parameter"}, status_code=400)
    result = auth_callback(code=code)
    return JSONResponse(result)

# Pour les endpoints SSE et Messages, nous montons l'application SSE de FastMCP.
# La méthode sse_app() de FastMCP renvoie une instance de Starlette qui gère /sse et /messages.
app.mount("/", mcp.sse_app())

# --- Fonctions utilitaires GTFS (les mêmes que précédemment) ---
def _fetch_feed(feed_type: str, is_json: bool = False, is_static: bool = False) -> Optional[Any]:
    now = time.time()
    cache = _cache[feed_type]
    if now - cache["timestamp"] < REFRESH_INTERVAL and cache["data"]:
        logging.debug(f"Returning cached data for {feed_type}")
        return cache["data"]
    try:
        url = NETWORK_URLS[NETWORK][feed_type]
        logging.info(f"Fetching {feed_type} from {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        if is_static:
            data = response.content
            logging.info(f"OK {feed_type} - GTFS static file downloaded (not parsed)")
        elif is_json:
            data = response.json()
            logging.info(f"OK {feed_type} - JSON data fetched ({len(data) if isinstance(data, list) else 'dict'})")
        else:
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
            data = feed
            logging.info(f"OK {feed_type} - {len(feed.entity)} entities")
        cache["data"] = data
        cache["timestamp"] = now
        cache["last_update"] = datetime.now().isoformat()
        return data
    except Exception as e:
        logging.error(f"Error fetching {feed_type}: {str(e)}")
        return cache["data"] if cache["data"] else None

def _get_vehicle_positions_data() -> List[Dict]:
    feed = _fetch_feed("vehicle_positions")
    if feed:
        return _parse_vehicle_positions(feed)
    return []

def _get_trip_updates_data() -> List[Dict]:
    feed = _fetch_feed("trip_updates")
    if feed:
        return _parse_trip_updates(feed)
    return []

def _get_service_alerts_data() -> List[Dict]:
    feed = _fetch_feed("service_alerts")
    if feed:
        return _parse_service_alerts(feed)
    return []

def _parse_vehicle_positions(feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
    data = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        vp = entity.vehicle
        vehicle_info = {
            "vehicle_id": entity.id or (vp.vehicle.id if vp.vehicle.HasField("id") else vp.vehicle.label),
            "latitude": vp.position.latitude if vp.position else None,
            "longitude": vp.position.longitude if vp.position else None,
            "bearing": vp.position.bearing if vp.position.HasField("bearing") else None,
            "speed": vp.position.speed if vp.position.HasField("speed") else None,
            "trip_id": vp.trip.trip_id if vp.HasField("trip") else None,
            "route_id": vp.trip.route_id if vp.HasField("trip") else None,
            "start_time": vp.trip.start_time if vp.HasField("trip") else None,
            "start_date": vp.trip.start_date if vp.HasField("trip") else None,
            "timestamp": vp.timestamp if vp.HasField("timestamp") else None,
        }
        data.append(vehicle_info)
    return data

def _parse_trip_updates(feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
    data = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        trip_info = {
            "trip_id": tu.trip.trip_id,
            "route_id": tu.trip.route_id,
            "start_time": tu.trip.start_time,
            "start_date": tu.trip.start_date,
            "vehicle_id": tu.vehicle.id if tu.vehicle.HasField("id") else None,
            "stop_time_updates": [
                {
                    "stop_id": stu.stop_id,
                    "arrival_delay": stu.arrival.delay if stu.HasField("arrival") and stu.arrival.HasField("delay") else 0,
                    "departure_delay": stu.departure.delay if stu.HasField("departure") and stu.departure.HasField("delay") else 0,
                    "arrival_time": stu.arrival.time if stu.HasField("arrival") and stu.arrival.HasField("time") else None,
                    "departure_time": stu.departure.time if stu.HasField("departure") and stu.departure.HasField("time") else None,
                    "schedule_relationship": str(stu.schedule_relationship),
                }
                for stu in tu.stop_time_update
            ],
        }
        data.append(trip_info)
    return data

def _parse_service_alerts(feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
    cause_map = {
        1: "UNKNOWN_CAUSE", 2: "OTHER_CAUSE", 3: "TECHNICAL_PROBLEM", 4: "STRIKE",
        5: "DEMONSTRATION", 6: "ACCIDENT", 7: "HOLIDAY", 8: "WEATHER",
        9: "MAINTENANCE", 10: "CONSTRUCTION", 11: "POLICE_ACTIVITY", 12: "MEDICAL_EMERGENCY"
    }
    effect_map = {
        1: "NO_SERVICE", 2: "REDUCED_SERVICE", 3: "SIGNIFICANT_DELAYS",
        4: "DETOUR", 5: "ADDITIONAL_SERVICE", 6: "MODIFIED_SERVICE",
        7: "OTHER_EFFECT", 8: "UNKNOWN_EFFECT", 9: "STOP_MOVED"
    }
    data = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue
        alert = entity.alert
        alert_info = {
            "alert_id": entity.id,
            "cause": cause_map.get(alert.cause, "UNKNOWN_CAUSE") if alert.HasField("cause") else None,
            "effect": effect_map.get(alert.effect, "UNKNOWN_EFFECT") if alert.HasField("effect") else None,
            "active_periods": [
                {"start": p.start, "end": p.end}
                for p in alert.active_period
                if p.HasField("start") or p.HasField("end")
            ],
            "routes": [ie.route_id for ie in alert.informed_entity if ie.HasField("route_id")],
            "stops": [ie.stop_id for ie in alert.informed_entity if ie.HasField("stop_id")],
            "description": alert.description_text.translation[0].text if alert.description_text.translation else None,
            "header": alert.header_text.translation[0].text if alert.header_text.translation else None,
        }
        data.append(alert_info)
    return data

def _parse_open_agenda(data: Dict) -> List[Dict]:
    events = data.get("events", []) if isinstance(data, dict) else data
    return [
        {
            "uid": event.get("uid"),
            "title": event.get("title", {}).get("fr"),
            "description": event.get("description", {}).get("fr"),
            "location": event.get("location", {}).get("name"),
            "latitude": event.get("location", {}).get("latitude"),
            "longitude": event.get("location", {}).get("longitude"),
            "start_time": event.get("timings", [{}])[0].get("begin"),
            "end_time": event.get("timings", [{}])[0].get("end"),
        }
        for event in events
    ]

def _parse_weather_infoclimat(data: Dict) -> Dict:
    forecasts = {}
    for timestamp, values in data.items():
        if timestamp.startswith("20"):
            forecasts[timestamp] = {
                "temperature_2m": values.get("temperature", {}).get("2m"),
                "wind_speed": values.get("vent_moyen", {}).get("10m"),
                "wind_gusts": values.get("vent_rafales", {}).get("10m"),
                "wind_direction": values.get("vent_direction", {}).get("10m"),
                "precipitation": values.get("pluie"),
                "humidity": values.get("humidite", {}).get("2m"),
                "pressure": values.get("pression", {}).get("niveau_de_la_mer"),
            }
    return forecasts

# --- Outils MCP (tools et resources) ---
# Exemple d'outils MCP exposés via FastMCP
@mcp.tool("get_vehicles")
def get_vehicle_positions(token: str):
    username = verify_token(token)
    if not username:
        return {"status": "error", "message": "Invalid or missing token"}
    logging.info(f"User {username} accessed vehicle positions")
    return {
        "status": "success",
        "data": _get_vehicle_positions_data(),
        "lastUpdate": _cache["vehicle_positions"]["last_update"],
    }

@mcp.tool("get_trip_updates")
def get_trip_updates(token: str):
    username = verify_token(token)
    if not username:
        return {"status": "error", "message": "Invalid or missing token"}
    logging.info(f"User {username} accessed trip updates")
    return {
        "status": "success",
        "data": _get_trip_updates_data(),
        "lastUpdate": _cache["trip_updates"]["last_update"],
    }

@mcp.tool("get_alerts")
def get_service_alerts(token: str):
    username = verify_token(token)
    if not username:
        return {"status": "error", "message": "Invalid or missing token"}
    logging.info(f"User {username} accessed service alerts")
    return {
        "status": "success",
        "data": _get_service_alerts_data(),
        "lastUpdate": _cache["service_alerts"]["last_update"],
    }

@mcp.tool("get_events")
def get_open_agenda_events(token: str):
    username = verify_token(token)
    if not username:
        return {"status": "error", "message": "Invalid or missing token"}
    logging.info(f"User {username} accessed events")
    data = _fetch_feed("open_agenda", is_json=True)
    return {
        "status": "success",
        "data": _parse_open_agenda(data) if data else [],
        "lastUpdate": _cache["open_agenda"]["last_update"],
    }

@mcp.tool("get_weather_forecast")
def get_weather_forecast(token: str):
    username = verify_token(token)
    if not username:
        return {"status": "error", "message": "Invalid or missing token"}
    logging.info(f"User {username} accessed weather forecast")
    data = _fetch_feed("weather_infoclimat", is_json=True)
    return {
        "status": "success",
        "data": _parse_weather_infoclimat(data) if data else {},
        "lastUpdate": _cache["weather_infoclimat"]["last_update"],
    }

# --- Exécution ---
if __name__ == "__main__":
    # Intégration complète via FastAPI :
    # La route /tools/auth_callback est gérée par FastAPI
    # et nous montons l'application SSE de FastMCP afin que /sse et /messages soient accessibles.
    from fastapi import FastAPI, Request
    from starlette.responses import JSONResponse

    app = FastAPI()

    @app.get("/tools/auth_callback")
    async def auth_callback_get(request: Request):
        code = request.query_params.get("code")
        if not code:
            return JSONResponse({"status": "error", "message": "Missing code parameter"}, status_code=400)
        result = auth_callback(code=code)
        return JSONResponse(result)

    # Monter l'application SSE de FastMCP.
    # La méthode sse_app() renvoie une instance Starlette qui gère /sse et /messages.
    app.mount("/", mcp.sse_app())

    logging.info(f"Starting integrated server on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
