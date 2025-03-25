#!/bin/bash

# Variables d'environnement pour le serveur MCP
export PORT=8000
export HOST="0.0.0.0"
export JWT_SECRET_KEY="secret-key-for-dev-only-please-change-in-production"

# Lancer le serveur
python app.py
