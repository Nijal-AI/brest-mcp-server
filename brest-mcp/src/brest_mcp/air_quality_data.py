"""
Module pour récupérer et traiter les données de qualité de l'air pour Brest.
"""
import os
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# URLs des APIs pour les données de qualité de l'air
AIR_QUALITY_API_URL = os.getenv("AIR_QUALITY_API_URL", "https://api.waqi.info/feed/brest/")
AIR_QUALITY_API_KEY = os.getenv("AIR_QUALITY_API_KEY", "")  # Clé API à configurer

# URL alternative pour Air Breizh (API locale)
AIR_BREIZH_API_URL = os.getenv("AIR_BREIZH_API_URL", "https://data.airbreizh.asso.fr/api/v1/station/brest/")

def fetch_air_quality_data() -> Optional[Dict]:
    """
    Récupère les données de qualité de l'air pour Brest.
    
    Returns:
        Données de qualité de l'air ou None en cas d'erreur
    """
    # Essaie d'abord l'API WAQI si une clé est configurée
    if AIR_QUALITY_API_KEY:
        try:
            params = {"token": AIR_QUALITY_API_KEY}
            logging.info(f"Fetching air quality data from WAQI API")
            response = requests.get(AIR_QUALITY_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "ok":
                return data
        except Exception as e:
            logging.error(f"Error fetching air quality data from WAQI: {str(e)}")
    
    # Sinon, essaie l'API Air Breizh
    try:
        logging.info(f"Fetching air quality data from Air Breizh API")
        response = requests.get(AIR_BREIZH_API_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching air quality data from Air Breizh: {str(e)}")
        return None

def parse_air_quality_data(data: Dict) -> Dict:
    """
    Parse les données de qualité de l'air.
    
    Args:
        data: Données brutes de l'API
    
    Returns:
        Données de qualité de l'air formatées
    """
    if not data:
        return {}
    
    # Format pour l'API WAQI
    if "data" in data and isinstance(data["data"], dict):
        waqi_data = data["data"]
        return {
            "aqi": waqi_data.get("aqi"),
            "station": waqi_data.get("city", {}).get("name", "Brest"),
            "timestamp": waqi_data.get("time", {}).get("iso"),
            "pollutants": {
                "pm25": waqi_data.get("iaqi", {}).get("pm25", {}).get("v"),
                "pm10": waqi_data.get("iaqi", {}).get("pm10", {}).get("v"),
                "o3": waqi_data.get("iaqi", {}).get("o3", {}).get("v"),
                "no2": waqi_data.get("iaqi", {}).get("no2", {}).get("v"),
                "so2": waqi_data.get("iaqi", {}).get("so2", {}).get("v"),
                "co": waqi_data.get("iaqi", {}).get("co", {}).get("v")
            },
            "level": get_aqi_level(waqi_data.get("aqi", 0)),
            "source": "WAQI"
        }
    
    # Format pour l'API Air Breizh
    if "indice" in data or "polluants" in data:
        return {
            "aqi": data.get("indice", {}).get("valeur"),
            "station": data.get("station", {}).get("nom", "Brest"),
            "timestamp": data.get("date"),
            "pollutants": {
                "pm25": next((p.get("valeur") for p in data.get("polluants", []) if p.get("code") == "PM25"), None),
                "pm10": next((p.get("valeur") for p in data.get("polluants", []) if p.get("code") == "PM10"), None),
                "o3": next((p.get("valeur") for p in data.get("polluants", []) if p.get("code") == "O3"), None),
                "no2": next((p.get("valeur") for p in data.get("polluants", []) if p.get("code") == "NO2"), None),
                "so2": next((p.get("valeur") for p in data.get("polluants", []) if p.get("code") == "SO2"), None)
            },
            "level": data.get("indice", {}).get("qualificatif"),
            "source": "Air Breizh"
        }
    
    return {}

def get_aqi_level(aqi: int) -> str:
    """
    Détermine le niveau de qualité de l'air en fonction de l'indice AQI.
    
    Args:
        aqi: Indice de qualité de l'air
    
    Returns:
        Description du niveau de qualité de l'air
    """
    if aqi is None:
        return "Unknown"
    elif aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Moderate"
    elif aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    elif aqi <= 200:
        return "Unhealthy"
    elif aqi <= 300:
        return "Very Unhealthy"
    else:
        return "Hazardous"

def get_air_quality() -> Dict:
    """
    Récupère et formate les données de qualité de l'air actuelles.
    
    Returns:
        Données formatées de qualité de l'air
    """
    data = fetch_air_quality_data()
    if not data:
        return {
            "status": "error",
            "message": "Unable to fetch air quality data"
        }
    
    air_quality = parse_air_quality_data(data)
    if not air_quality:
        return {
            "status": "error",
            "message": "Unable to parse air quality data"
        }
    
    return {
        "status": "success",
        "data": air_quality,
        "lastUpdate": datetime.now().isoformat()
    }

def get_health_recommendations(aqi: int) -> Dict:
    """
    Fournit des recommandations de santé basées sur l'indice de qualité de l'air.
    
    Args:
        aqi: Indice de qualité de l'air
    
    Returns:
        Recommandations de santé
    """
    if aqi is None:
        return {
            "general": "Données de qualité d'air non disponibles",
            "sensitive_groups": "Consultez les prévisions locales",
            "outdoor_activity": "Pas de recommandation spécifique"
        }
    
    if aqi <= 50:
        return {
            "general": "La qualité de l'air est considérée comme satisfaisante",
            "sensitive_groups": "Pas de risque pour la santé",
            "outdoor_activity": "Activités extérieures normales"
        }
    elif aqi <= 100:
        return {
            "general": "La qualité de l'air est acceptable",
            "sensitive_groups": "Les personnes très sensibles peuvent ressentir des symptômes",
            "outdoor_activity": "Activités extérieures normales"
        }
    elif aqi <= 150:
        return {
            "general": "Les personnes sensibles peuvent ressentir des effets sur la santé",
            "sensitive_groups": "Réduire les activités extérieures prolongées",
            "outdoor_activity": "Tout le monde devrait réduire les efforts prolongés en extérieur"
        }
    elif aqi <= 200:
        return {
            "general": "Tout le monde peut commencer à ressentir des effets sur la santé",
            "sensitive_groups": "Éviter les activités extérieures prolongées",
            "outdoor_activity": "Tout le monde devrait limiter les efforts en extérieur"
        }
    elif aqi <= 300:
        return {
            "general": "Avertissements sanitaires, tout le monde peut ressentir des effets plus graves",
            "sensitive_groups": "Éviter toute activité extérieure",
            "outdoor_activity": "Tout le monde devrait éviter les efforts en extérieur"
        }
    else:
        return {
            "general": "Alerte sanitaire : tout le monde peut ressentir des effets sanitaires graves",
            "sensitive_groups": "Rester à l'intérieur et maintenir un niveau d'activité faible",
            "outdoor_activity": "Tout le monde devrait éviter toute activité en extérieur"
        }

def get_air_quality_with_recommendations() -> Dict:
    """
    Récupère les données de qualité de l'air avec des recommandations de santé.
    
    Returns:
        Données de qualité de l'air avec recommandations
    """
    air_quality_data = get_air_quality()
    
    if air_quality_data.get("status") == "error":
        return air_quality_data
    
    aqi = air_quality_data.get("data", {}).get("aqi")
    recommendations = get_health_recommendations(aqi)
    
    air_quality_data["data"]["recommendations"] = recommendations
    return air_quality_data
