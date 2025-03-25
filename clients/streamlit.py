import streamlit as st
import asyncio
import os
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.stdio import sse_client, stdio_client, StdioServerParameters
from mcp.types import ListToolsResult, ReadResourceResult
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import json
from contextlib import AsyncExitStack
from datetime import datetime
import ollama
import threading

# Charger les variables d'environnement
load_dotenv()

# Configuration de Streamlit
st.set_page_config(
    page_title="MCP Transit Dashboard",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded"
)

class MCPStreamlitClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.tools = []
        self.resources = []
        self.server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "mcp_gtfs", "server.py")
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def connect_to_server(self):
            """Connexion au serveur MCP via SSE."""
            try:
                async with sse_client(f"http://{self.host}:{self.port}/events") as client:
                    self.session = await self.exit_stack.enter_async_context(ClientSession(client, client))
                    await self.session.initialize()
                    tools_resp: ListToolsResult = await self.session.list_tools()
                    self.tools = [
                        {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema}
                        for tool in tools_resp.tools
                    ]
                    resources_resp = await self.session.list_resources()
                    self.resources = [res.name for res in resources_resp.resources]
                    return True
            except Exception as e:
                st.error(f"Erreur de connexion au serveur SSE : {e}")
                return False

    async def call_tool(self, tool_name: str, args: dict = {}):
        """Appelle un outil MCP via CallToolRequest."""
        if not self.session:
            return {"status": "error", "message": "Non connecté au serveur"}
        try:
            result = await self.session.call_tool(tool_name, args)
            return json.loads(result.content) if result.content else {}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def read_resource(self, resource_path: str):
        """Lit une ressource MCP via ReadResourceRequest."""
        if not self.session:
            return {"status": "error", "message": "Non connecté au serveur"}
        try:
            result: ReadResourceResult = await self.session.read_resource(resource_path)
            return json.loads(result.content) if result.content else {}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def cleanup(self):
        """Ferme la connexion proprement."""
        try:
            await self.exit_stack.aclose()
            self.session = None
        except Exception as e:
            st.error(f"Erreur lors de la fermeture : {e}")
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def run_async(self, coro):
        """Exécute une coroutine dans la boucle persistante."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

# Initialisation du client
client = MCPStreamlitClient()

# Gestion de la connexion
if "connected" not in st.session_state:
    st.session_state.connected = False
    st.session_state.tools = []
    st.session_state.resources = []

if not st.session_state.connected:
    with st.spinner("Connexion au serveur MCP..."):
        st.session_state.connected = client.run_async(client.connect_to_server())
        if st.session_state.connected:
            st.session_state.tools = client.tools
            st.session_state.resources = client.resources
            st.success(f"Connecté au serveur MCP ! Outils : {len(st.session_state.tools)}, Ressources : {len(st.session_state.resources)}")
        else:
            st.error("Échec de la connexion au serveur.")
            st.stop()

# Sidebar avec navigation
st.sidebar.title("🚍 MCP Transit Dashboard")
page = st.sidebar.radio(
    "Navigation",
    ["Accueil", "Véhicules", "Trajets", "Alertes", "Événements", "Météo", "Statistiques", "Réseaux"]
)

# Fonctions utilitaires
def fetch_tool_data(tool_name: str, args: dict = {}):
    result = client.run_async(client.call_tool(tool_name, args))
    return result.get("data") if result.get("status") == "success" else None

def fetch_resource_data(resource_path: str):
    result = client.run_async(client.read_resource(resource_path))
    return result.get("data") if result.get("status") == "success" else None

# Interaction avec LLM
def query_llm(query: str, tools: list):
    system_prompt = "Vous êtes un assistant utile pour le MCP Transit Dashboard. Voici les outils disponibles :\n"
    for tool in tools:
        system_prompt += f"- {tool['name']}: {tool['description']}\n"
    system_prompt += "Répondez à la requête ou utilisez [tool_name: args] pour appeler un outil si nécessaire."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
    
    try:
        response = ollama.chat(model="llama3.2", messages=messages)
        return response['message']['content']
    except Exception as e:
        return f"Erreur LLM : {e}"

# Page d'accueil avec prompt LLM
if page == "Accueil":
    st.title("Bienvenue sur le MCP Transit Dashboard")
    st.markdown("""
        Explorez en temps réel les données de transport public (Bibus), les événements locaux, et la météo à Brest.
        Posez une question ci-dessous pour interagir avec l'assistant IA !
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        vehicle_count = fetch_tool_data("count_vehicles")
        st.metric("Véhicules actifs", vehicle_count if vehicle_count is not None else "N/A")
    with col2:
        alert_count = fetch_tool_data("count_alerts")
        st.metric("Alertes actives", alert_count if alert_count is not None else "N/A")
    
    st.subheader("💬 Posez une question à l'assistant")
    user_query = st.text_input("Entrez votre question (ex. 'Combien de véhicules sur la ligne A ?')")
    if user_query:
        with st.spinner("Réponse en cours..."):
            answer = query_llm(user_query, st.session_state.tools)
            st.write(f"**Assistant** : {answer}")
            if "[" in answer and "]" in answer:
                import re
                tool_pattern = r'\[(.*?):(.*?)\]'
                tool_match = re.search(tool_pattern, answer)
                if tool_match:
                    tool_name, tool_args = tool_match.groups()
                    try:
                        args = json.loads(tool_args) if tool_args else {}
                        tool_result = fetch_tool_data(tool_name, args)
                        st.write(f"**Résultat de l'outil {tool_name}** : {tool_result}")
                    except Exception as e:
                        st.error(f"Erreur lors de l'appel de l'outil : {e}")

# Page Véhicules
elif page == "Véhicules":
    st.title("🚌 Suivi des Véhicules")
    vehicles_data = fetch_resource_data("gtfs://vehicles")
    if vehicles_data:
        df_vehicles = pd.DataFrame(vehicles_data)
        if not df_vehicles.empty:
            m = folium.Map(location=[48.3904, -4.4861], zoom_start=12)
            for _, row in df_vehicles.iterrows():
                if row.get("latitude") and row.get("longitude"):
                    folium.Marker(
                        [row["latitude"], row["longitude"]],
                        popup=f"Véhicule {row.get('vehicle_id', 'N/A')}<br>Route: {row.get('route_id', 'N/A')}",
                        icon=folium.Icon(color="blue", icon="bus", prefix="fa")
                    ).add_to(m)
            st_folium(m, width=700, height=500)
        
        route_id = st.selectbox("Filtrer par ligne", ["Toutes"] + sorted(df_vehicles["route_id"].dropna().unique()))
        if route_id != "Toutes":
            filtered_vehicles = fetch_tool_data("find_vehicles_by_route", {"route_id": route_id})
            df_vehicles = pd.DataFrame(filtered_vehicles) if filtered_vehicles else pd.DataFrame()
        
        st.dataframe(df_vehicles, use_container_width=True)
    else:
        st.error("Impossible de charger les données des véhicules.")

# Page Trajets
elif page == "Trajets":
    st.title("🛤️ Mises à jour des Trajets")
    trips_data = fetch_tool_data("get_trip_updates")
    if trips_data:
        df_trips = pd.DataFrame(trips_data)
        route_id = st.selectbox("Filtrer par ligne", ["Toutes"] + sorted(df_trips["route_id"].dropna().unique()))
        if route_id != "Toutes":
            filtered_trips = fetch_tool_data("find_trips_by_route", {"route_id": route_id})
            df_trips = pd.DataFrame([t for t in trips_data if t["trip_id"] in filtered_trips]) if filtered_trips else pd.DataFrame()
        
        if not df_trips.empty:
            trip_id = st.selectbox("Sélectionner un trajet", df_trips["trip_id"])
            trip_details = next((t for t in trips_data if t["trip_id"] == trip_id), None)
            if trip_details:
                st.json(trip_details)
                stops_df = pd.DataFrame(trip_details.get("stop_time_updates", []))
                if not stops_df.empty:
                    fig = px.bar(stops_df, x="stop_id", y="arrival_delay", title="Retards par arrêt")
                    st.plotly_chart(fig)
    else:
        st.error("Impossible de charger les mises à jour des trajets.")

# Page Alertes
elif page == "Alertes":
    st.title("⚠️ Alertes de Service")
    alerts_data = fetch_tool_data("get_alerts")
    if alerts_data:
        df_alerts = pd.DataFrame(alerts_data)
        if not df_alerts.empty:
            route_id = st.selectbox("Filtrer par ligne", ["Toutes"] + sorted(set([r for a in df_alerts["routes"] for r in a])))
            if route_id != "Toutes":
                filtered_alerts = fetch_tool_data("find_alerts_by_route", {"route_id": route_id})
                df_alerts = pd.DataFrame(filtered_alerts) if filtered_alerts else pd.DataFrame()
            
            for _, alert in df_alerts.iterrows():
                with st.expander(f"{alert.get('header', 'N/A')} (ID: {alert.get('alert_id', 'N/A')})"):
                    st.write(f"**Cause**: {alert.get('cause', 'N/A')}")
                    st.write(f"**Effet**: {alert.get('effect', 'N/A')}")
                    st.write(f"**Description**: {alert.get('description', 'N/A')}")
                    st.write(f"**Période**: {alert.get('active_periods', [{}])[0].get('start', 'N/A')} - {alert.get('active_periods', [{}])[0].get('end', 'N/A')}")
                    st.write(f"**Routes affectées**: {', '.join(alert.get('routes', []))}")
    else:
        st.error("Impossible de charger les alertes.")

# Page Événements
elif page == "Événements":
    st.title("🎉 Événements à Brest")
    events_data = fetch_resource_data("gtfs://events")
    if events_data:
        df_events = pd.DataFrame(events_data)
        if not df_events.empty:
            m = folium.Map(location=[48.3904, -4.4861], zoom_start=12)
            for _, event in df_events.iterrows():
                if event.get("latitude") and event.get("longitude"):
                    folium.Marker(
                        [event["latitude"], event["longitude"]],
                        popup=f"{event.get('title', 'N/A')}<br>{event.get('start_time', 'N/A')}",
                        icon=folium.Icon(color="green", icon="calendar", prefix="fa")
                    ).add_to(m)
            st_folium(m, width=700, height=500)
            st.dataframe(df_events[["title", "start_time", "end_time", "location"]], use_container_width=True)
    else:
        st.error("Impossible de charger les événements.")

# Page Météo
elif page == "Météo":
    st.title("☀️ Prévisions Météo")
    weather_data = fetch_resource_data("gtfs://weather")
    if weather_data:
        df_weather = pd.DataFrame.from_dict(weather_data, orient="index")
        df_weather.index = pd.to_datetime(df_weather.index)
        
        date_range = st.slider(
            "Plage temporelle",
            min_value=df_weather.index.min().to_pydatetime(),
            max_value=df_weather.index.max().to_pydatetime(),
            value=(df_weather.index.min().to_pydatetime(), df_weather.index.max().to_pydatetime()),
            format="YYYY-MM-DD HH:mm"
        )
        df_weather_filtered = df_weather.loc[date_range[0]:date_range[1]]
        
        col1, col2 = st.columns(2)
        with col1:
            fig_temp = px.line(df_weather_filtered, y="temperature_2m", title="Température (2m)")
            st.plotly_chart(fig_temp)
        with col2:
            fig_wind = px.line(df_weather_filtered, y="wind_speed", title="Vitesse du vent")
            st.plotly_chart(fig_wind)
        
        st.dataframe(df_weather_filtered, use_container_width=True)
    else:
        st.error("Impossible de charger les données météo.")

# Page Statistiques
elif page == "Statistiques":
    st.title("📊 Statistiques du Réseau")
    stats_data = fetch_resource_data("gtfs://network/stats")
    if stats_data:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Véhicules totaux", stats_data.get("totalVehicles", "N/A"))
        with col2:
            st.metric("Retard moyen (s)", f"{stats_data.get('averageDelay', 0):.2f}")
        with col3:
            st.metric("Performance à l'heure (%)", f"{stats_data.get('onTimePerformance', 0):.1f}")
        
        status_df = pd.DataFrame(stats_data.get("vehiclesByStatus", {}).items(), columns=["Statut", "Nombre"])
        fig_status = px.pie(status_df, names="Statut", values="Nombre", title="Véhicules par statut")
        st.plotly_chart(fig_status)
    else:
        st.error("Impossible de charger les statistiques.")

# Page Réseaux
elif page == "Réseaux":
    st.title("🌐 Réseaux Disponibles")
    networks_data = fetch_resource_data("gtfs://networks")
    if networks_data:
        df_networks = pd.DataFrame(networks_data)
        selected_network = st.selectbox("Sélectionner un réseau", df_networks["id"])
        if selected_network:
            resource_path = f"gtfs://network/{selected_network}/vehicles"
            network_vehicles = fetch_resource_data(resource_path)
            if network_vehicles:
                df_network_vehicles = pd.DataFrame(network_vehicles)
                if not df_network_vehicles.empty:
                    m = folium.Map(location=[48.3904, -4.4861], zoom_start=12)
                    for _, row in df_network_vehicles.iterrows():
                        if row.get("position", {}).get("latitude") and row.get("position", {}).get("longitude"):
                            folium.Marker(
                                [row["position"]["latitude"], row["position"]["longitude"]],
                                popup=f"Véhicule {row.get('vehicle_id', 'N/A')}<br>Route: {row.get('route_id', 'N/A')}",
                                icon=folium.Icon(color="purple", icon="bus", prefix="fa")
                            ).add_to(m)
                    st_folium(m, width=700, height=500)
                    st.dataframe(df_network_vehicles)
            else:
                st.error("Impossible de charger les véhicules du réseau.")
    else:
        st.error("Impossible de charger les réseaux.")

# Pied de page
st.sidebar.markdown("---")
st.sidebar.write(f"Dernière mise à jour : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
if st.sidebar.button("Déconnexion"):
    client.run_async(client.cleanup())
    st.session_state.connected = False
    st.rerun()

# Gestion de la fermeture
def on_exit():
    if st.session_state.connected:
        client.run_async(client.cleanup())

import atexit
atexit.register(on_exit)