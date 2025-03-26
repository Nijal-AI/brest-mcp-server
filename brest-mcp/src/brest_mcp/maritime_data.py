"""
Module pour récupérer et traiter les données maritimes et de marées pour Brest.
"""
import os
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# URLs des APIs pour les données maritimes
TIDES_API_URL = os.getenv("SHOM_TIDES_API_URL", "https://services.data.shom.fr/b2q8lrcdl4s04cbabsj4nhcb/hdm/spm/water-level")
TIDES_API_KEY = os.getenv("SHOM_TIDES_API_KEY", "")  # Clé API à configurer
PORT_ID = os.getenv("SHOM_PORT_ID", "BREST")  # ID du port de Brest

def fetch_tide_data(days: int = 2) -> Optional[Dict]:
    """
    Récupère les données de marées pour le port de Brest.
    
    Args:
        days: Nombre de jours de prévision (1 à 7)
    
    Returns:
        Données de marées ou None en cas d'erreur
    """
    if not TIDES_API_KEY:
        logging.warning("SHOM API key not configured. Set SHOM_TIDES_API_KEY environment variable.")
        return None
    
    try:
        # Calcul des dates de début et de fin
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Paramètres de la requête
        params = {
            "harborName": PORT_ID,
            "startDate": start_date,
            "endDate": end_date,
            "step": 15,  # Intervalle en minutes
            "datum": "LAT",  # Niveau de référence (Lowest Astronomical Tide)
            "waterLevelUnit": "m",  # Unité en mètres
            "apiKey": TIDES_API_KEY
        }
        
        logging.info(f"Fetching tide data for {PORT_ID} from {start_date} to {end_date}")
        response = requests.get(TIDES_API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching tide data: {str(e)}")
        return None

def parse_tide_data(data: Dict) -> List[Dict]:
    """
    Parse les données de marées du SHOM.
    
    Args:
        data: Données brutes de l'API SHOM
    
    Returns:
        Liste des prédictions de marées formatées
    """
    if not data or "data" not in data:
        return []
    
    tides = []
    for item in data.get("data", []):
        tide = {
            "timestamp": item.get("datetime"),
            "water_level": item.get("height"),
            "tide_type": "HIGH" if item.get("high_tide", False) else "LOW" if item.get("low_tide", False) else "INTERMEDIATE",
            "coefficient": item.get("coefficient")
        }
        tides.append(tide)
    
    return tides

def get_next_tides(count: int = 4) -> List[Dict]:
    """
    Récupère les prochaines marées (hautes et basses).
    
    Args:
        count: Nombre de marées à récupérer
    
    Returns:
        Liste des prochaines marées
    """
    data = fetch_tide_data()
    if not data:
        return []
    
    tides = parse_tide_data(data)
    
    # Filtre uniquement les marées hautes et basses
    high_low_tides = [t for t in tides if t.get("tide_type") in ["HIGH", "LOW"]]
    
    # Trie par timestamp et limite le nombre de résultats
    high_low_tides.sort(key=lambda x: x.get("timestamp", ""))
    return high_low_tides[:count]

def get_tide_by_date(date: str) -> List[Dict]:
    """
    Récupère les marées pour une date spécifique.
    
    Args:
        date: Date au format YYYY-MM-DD
    
    Returns:
        Liste des marées pour la date spécifiée
    """
    data = fetch_tide_data(7)  # Récupère une semaine de données
    if not data:
        return []
    
    tides = parse_tide_data(data)
    
    # Filtre les marées pour la date spécifiée
    return [t for t in tides if t.get("timestamp", "").startswith(date)]

def get_current_tide_status() -> Dict:
    """
    Détermine le statut actuel de la marée (montante/descendante).
    
    Returns:
        Informations sur le statut actuel de la marée
    """
    data = fetch_tide_data()
    if not data:
        return {
            "status": "error",
            "message": "Unable to fetch tide data"
        }
    
    tides = parse_tide_data(data)
    if not tides:
        return {
            "status": "error",
            "message": "No tide data available"
        }
    
    # Trie par timestamp
    tides.sort(key=lambda x: x.get("timestamp", ""))
    
    # Trouve l'index de la marée actuelle
    now = datetime.now().isoformat()
    current_index = 0
    for i, tide in enumerate(tides):
        if tide.get("timestamp", "") > now:
            current_index = i - 1 if i > 0 else 0
            break
    
    current_tide = tides[current_index]
    next_tide = tides[current_index + 1] if current_index + 1 < len(tides) else None
    
    # Détermine si la marée est montante ou descendante
    is_rising = False
    if next_tide:
        is_rising = next_tide.get("water_level", 0) > current_tide.get("water_level", 0)
    
    return {
        "status": "success",
        "current_level": current_tide.get("water_level"),
        "timestamp": current_tide.get("timestamp"),
        "tide_direction": "RISING" if is_rising else "FALLING",
        "next_high_tide": next((t for t in tides[current_index:] if t.get("tide_type") == "HIGH"), None),
        "next_low_tide": next((t for t in tides[current_index:] if t.get("tide_type") == "LOW"), None)
    }
