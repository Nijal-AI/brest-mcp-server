import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import json

NETWORK_URLS = {
    "bibus": {
        "vehicle_positions": "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-vehicle-position",
        "trip_updates": "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-trip-update",
        "service_alerts": "https://proxy.transport.data.gouv.fr/resource/bibus-brest-gtfs-rt-alerts",
        "gtfs_static": "https://s3.eu-west-1.amazonaws.com/files.orchestra.ratpdev.com/networks/bibus/exports/medias.zip",
        "open_agenda": "https://api.openagenda.com/v2/events?search=brest&limit=10&key=cf7141c803f746f0abec6bb1667d55e2",
        "weather_infoclimat": "https://www.infoclimat.fr/public-api/gfs/json?_ll=48.4475,-4.4181&_auth=ARtTRAV7ByVec1FmAnRVfFU9BzIMegIlVCgDYA1oVyoDaFIzVTVcOlE%2FBnsHKFZgBypXNFphU2MCaVAoD31RMAFrUz8FbgdgXjFRNAItVX5VewdmDCwCJVQ1A2QNflc9A2dSKFU3XDZRNwZ6Bz5WZAcrVyhaZFNsAmVQNQ9nUTYBZFM1BWYHbV4uUSwCNFVmVTIHMwwxAj9UNQNkDWRXNwNgUmBVN1w3USAGZwc%2BVmcHPVc2Wm1TbwJkUCgPfVFLARFTKgUmBydeZFF1Ai9VNFU4BzM%3D&_c=38fc48e42684d2b24279d0b02e2d0713"
    }
}

def fetch_feed(url: str, is_static=False, is_json=False) -> dict | gtfs_realtime_pb2.FeedMessage | None:
    try:
        print(f"GET {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        if is_static:
            print(f"OK {url} - GTFS static file downloaded (not parsed)")
            return response.content
        elif is_json:
            data = response.json()
            print(f"OK {url} - JSON data fetched ({len(data) if isinstance(data, list) else 'dict'})")
            return data
        else:
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
            print(f"OK {url} - {len(feed.entity)} entities")
            return feed
    except Exception as e:
        print(f"ERR {url}: {e}")
        return None

def get_type_and_value(value):
    if value is None:
        return "null", None
    if isinstance(value, int):
        return "int", value
    if isinstance(value, float):
        return "float", value
    if isinstance(value, str):
        return "str", value
    if isinstance(value, list):
        inner_type = get_type_and_value(value[0])[0] if value else "any"
        return f"list[{inner_type}]", value[0] if value else None
    if isinstance(value, dict):
        return "dict", None
    return "unknown", str(value)

def extract_keys(obj, prefix=""):
    result = {}
    if not obj or (hasattr(obj, "DESCRIPTOR") and not obj.DESCRIPTOR.fields):
        return result
    if hasattr(obj, "DESCRIPTOR"):  # Pour Protobuf
        for field in obj.DESCRIPTOR.fields:
            key = f"{prefix}{field.name}"
            value = getattr(obj, field.name)
            type_, val = get_type_and_value(value)
            result[key] = {"type": type_, "value": val}
            if field.type == field.TYPE_MESSAGE:
                if field.label == field.LABEL_REPEATED and value and len(value) > 0:
                    nested = extract_keys(value[0], f"{key}.")
                    result.update(nested)
                elif value:
                    nested = extract_keys(value, f"{key}.")
                    result.update(nested)
    elif isinstance(obj, dict):  # Pour JSON
        for key, value in obj.items():
            full_key = f"{prefix}{key}"
            type_, val = get_type_and_value(value)
            result[full_key] = {"type": type_, "value": val}
            if isinstance(value, dict):
                nested = extract_keys(value, f"{full_key}.")
                result.update(nested)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                nested = extract_keys(value[0], f"{full_key}.")
                result.update(nested)
    return result

def analyze_gtfs_data():
    summary = {"timestamp": datetime.now().isoformat(), "networks": {}}

    for network, feeds in NETWORK_URLS.items():
        print(f"\n=== {network} ===")
        summary["networks"][network] = {}

        for feed_type, url in feeds.items():
            is_static = feed_type == "gtfs_static"
            is_json = feed_type in ["open_agenda", "weather_infoclimat"]
            feed = fetch_feed(url, is_static, is_json)
            
            if feed and not is_static and not is_json and feed.entity:
                entity = feed.entity[0]
                keys_types_values = extract_keys(entity)
                summary["networks"][network][feed_type] = keys_types_values
                print(f"{feed_type}: {len(feed.entity)} entities")
                for key, info in keys_types_values.items():
                    val_str = f" = {info['value']}" if info["value"] is not None else ""
                    print(f"  {key}: {info['type']}{val_str}")
            elif is_static and feed:
                summary["networks"][network][feed_type] = "raw GTFS static data (zip file)"
                print(f"{feed_type}: Downloaded (not parsed)")
            elif is_json and feed:
                keys_types_values = extract_keys(feed if not isinstance(feed, list) else feed[0])
                summary["networks"][network][feed_type] = keys_types_values
                print(f"{feed_type}: JSON data")
                for key, info in keys_types_values.items():
                    val_str = f" = {info['value']}" if info["value"] is not None else ""
                    print(f"  {key}: {info['type']}{val_str}")

    with open("gtfs-keys-summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nSummary saved to gtfs-keys-summary.json")

if __name__ == "__main__":
    analyze_gtfs_data()