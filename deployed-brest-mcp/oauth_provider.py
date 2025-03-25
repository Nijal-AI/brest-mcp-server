"""
Module d'authentification OAuth2 pour le serveur MCP de Brest
Inspiré par l'implémentation de Cloudflare pour remote-mcp-server
"""

import os
import time
import json
from typing import Dict, List, Optional, Any
from fastapi import Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc6749.tokens import BearerToken
from authlib.oauth2.rfc7636 import CodeChallenge
from authlib.oauth2 import AuthorizationServer
from authlib.common.security import generate_token
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import jwt

# Clé secrète pour signer les JWT
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "secret-key-for-dev-only-please-change-in-production")

# Durée de validité des jetons (en secondes)
TOKEN_EXPIRES_IN = 3600

# Stockage en mémoire pour les codes d'autorisation et les jetons
# Dans une application de production, utilisez une base de données
authorization_codes = {}
tokens = {}
user_authorizations = {}

# Modèle d'utilisateur
class User(BaseModel):
    email: str
    user_id: str
    is_active: bool = True

# Modèle de client OAuth
class OAuthClient:
    def __init__(self, client_id, client_secret, client_name, redirect_uris, allowed_scopes):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client_name = client_name
        self.redirect_uris = redirect_uris
        self.allowed_scopes = allowed_scopes
    
    def get_client_id(self):
        return self.client_id
    
    def get_default_redirect_uri(self):
        return self.redirect_uris[0] if self.redirect_uris else None
    
    def get_allowed_scope(self, scope):
        if not scope:
            return ' '.join(self.allowed_scopes)
        allowed = set(self.allowed_scopes)
        scopes = set(scope.split())
        return ' '.join(allowed.intersection(scopes))
    
    def check_redirect_uri(self, redirect_uri):
        return redirect_uri in self.redirect_uris
    
    def check_client_secret(self, client_secret):
        return self.client_secret == client_secret
    
    def check_token_endpoint_auth_method(self, method):
        return method == 'client_secret_post'

# Modèle de code d'autorisation
class AuthorizationCode(BaseModel):
    code: str
    client_id: str
    redirect_uri: str
    scope: str
    user_id: str
    expires_at: int

# Modèle de jeton
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str
    user_id: str

# Implémentation personnalisée du grant type "authorization_code"
class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    def create_authorization_code(self, client, grant_user, request):
        code = generate_token(48)
        expires_at = int(time.time()) + 600  # 10 minutes
        
        # Enregistrer le code d'autorisation
        authorization_codes[code] = AuthorizationCode(
            code=code,
            client_id=client.client_id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            user_id=grant_user,
            expires_at=expires_at
        )
        
        return code
    
    def parse_authorization_code(self, code, client):
        auth_code = authorization_codes.get(code)
        if not auth_code or auth_code.client_id != client.client_id:
            return None
        return auth_code
    
    def delete_authorization_code(self, authorization_code):
        if authorization_code.code in authorization_codes:
            del authorization_codes[authorization_code.code]
    
    def authenticate_user(self, authorization_code):
        return authorization_code.user_id

# Gestionnaire d'authentification
class OAuthProvider:
    def __init__(self, app=None):
        self.app = app
        self.server = None
        self._setup_oauth_server()
        
        if app:
            self.init_app(app)
    
    # Initialise l'application FastAPI avec le middleware de session et les routes OAuth
    def init_app(self, app):
        app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET_KEY)
        app.add_route("/oauth/authorize", self.authorize)
        app.add_route("/oauth/token", self.issue_token)
        app.add_route("/oauth/register", self.register_client)
        app.add_route("/login", self._render_login_page)
        app.add_route("/auth", self._authenticate_user_from_request)
        app.add_route("/logout", self._logout)
        app.add_route("/authorize/approve", self.approve)
    
    # Configure le serveur OAuth
    def _setup_oauth_server(self):
        def query_client(client_id):
            return self._get_client(client_id)
        
        def save_token(token, request):
            tokens[token["access_token"]] = Token(
                access_token=token["access_token"],
                token_type=token["token_type"],
                expires_in=token["expires_in"],
                refresh_token=token.get("refresh_token"),
                scope=token["scope"],
                user_id=request.user
            )
        
        # Créer le serveur d'autorisation
        self.server = AuthorizationServer(
            query_client=query_client,
            save_token=save_token
        )
        
        # Configurer les types de grant
        self.server.register_grant(AuthorizationCodeGrant())
        
        # Configurer le générateur de jetons
        self.server.register_token_generator(
            "default",
            BearerToken(expires_in=TOKEN_EXPIRES_IN)
        )
    
    # Point de terminaison d'autorisation OAuth
    async def authorize(self, request: Request):
        # Récupérer l'utilisateur actuel
        user = self._get_current_user(request)
        
        # Si l'utilisateur n'est pas connecté, rediriger vers la page de connexion
        if not user:
            redirect_uri = str(request.url)
            return RedirectResponse(url=f"/login?redirect_uri={redirect_uri}")
        
        # Récupérer les paramètres de la requête
        client_id = request.query_params.get("client_id")
        redirect_uri = request.query_params.get("redirect_uri")
        response_type = request.query_params.get("response_type")
        scope = request.query_params.get("scope", "")
        state = request.query_params.get("state", "")
        
        # Vérifier les paramètres requis
        if not client_id or not redirect_uri or response_type != "code":
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_request", "error_description": "Missing required parameters"}
            )
        
        # Vérifier si le client existe
        client = self._get_client(client_id)
        if not client:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_client", "error_description": "Unknown client"}
            )
        
        # Vérifier si l'URI de redirection est valide
        if not client.check_redirect_uri(redirect_uri):
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_request", "error_description": "Invalid redirect URI"}
            )
        
        # Vérifier si l'utilisateur a déjà autorisé ce client
        if self._has_user_authorized(user.user_id, client_id):
            # Générer un code d'autorisation
            code = generate_token(48)
            expires_at = int(time.time()) + 600  # 10 minutes
            
            # Enregistrer le code d'autorisation
            authorization_codes[code] = AuthorizationCode(
                code=code,
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=client.get_allowed_scope(scope),
                user_id=user.user_id,
                expires_at=expires_at
            )
            
            # Rediriger vers l'URI de redirection avec le code
            redirect_to = f"{redirect_uri}?code={code}"
            if state:
                redirect_to += f"&state={state}"
            
            return RedirectResponse(url=redirect_to)
        
        # Afficher la page d'autorisation
        return await self._render_authorization_page(
            request,
            {
                "client": client,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "state": state
            },
            user
        )
    
    # Traite l'approbation ou le rejet de l'autorisation OAuth
    async def approve(self, request: Request):
        form_data = await request.form()
        
        # Récupérer l'utilisateur actuel
        user = self._get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        # Récupérer les paramètres du formulaire
        client_id = form_data.get("client_id")
        redirect_uri = form_data.get("redirect_uri")
        scope = form_data.get("scope", "")
        state = form_data.get("state", "")
        action = form_data.get("action")
        
        # Vérifier si l'utilisateur a approuvé la demande
        if action != "approve":
            # Rediriger vers l'URI de redirection avec une erreur
            error_redirect = f"{redirect_uri}?error=access_denied"
            if state:
                error_redirect += f"&state={state}"
            
            return RedirectResponse(url=error_redirect)
        
        # Vérifier si le client existe
        client = self._get_client(client_id)
        if not client:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_client", "error_description": "Unknown client"}
            )
        
        # Enregistrer l'autorisation de l'utilisateur
        self._save_user_authorization(user.user_id, client_id)
        
        # Générer un code d'autorisation
        code = generate_token(48)
        expires_at = int(time.time()) + 600  # 10 minutes
        
        # Enregistrer le code d'autorisation
        authorization_codes[code] = AuthorizationCode(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=client.get_allowed_scope(scope),
            user_id=user.user_id,
            expires_at=expires_at
        )
        
        # Rediriger vers l'URI de redirection avec le code
        redirect_to = f"{redirect_uri}?code={code}"
        if state:
            redirect_to += f"&state={state}"
        
        return RedirectResponse(url=redirect_to)
    
    # Point de terminaison d'émission de jetons OAuth
    async def issue_token(self, request: Request):
        form_data = await request.form()
        
        # Récupérer les paramètres du formulaire
        grant_type = form_data.get("grant_type")
        code = form_data.get("code")
        redirect_uri = form_data.get("redirect_uri")
        client_id = form_data.get("client_id")
        client_secret = form_data.get("client_secret")
        
        # Vérifier les paramètres requis
        if not grant_type or grant_type != "authorization_code" or not code or not redirect_uri or not client_id or not client_secret:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_request", "error_description": "Missing required parameters"}
            )
        
        # Vérifier si le client existe
        client = self._get_client(client_id)
        if not client:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_client", "error_description": "Unknown client"}
            )
        
        # Vérifier si le secret du client est valide
        if not client.check_client_secret(client_secret):
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_client", "error_description": "Invalid client credentials"}
            )
        
        # Vérifier si le code d'autorisation existe
        auth_code = authorization_codes.get(code)
        if not auth_code:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_grant", "error_description": "Invalid authorization code"}
            )
        
        # Vérifier si le code d'autorisation est expiré
        if auth_code.expires_at < int(time.time()):
            # Supprimer le code d'autorisation expiré
            del authorization_codes[code]
            
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_grant", "error_description": "Authorization code expired"}
            )
        
        # Vérifier si le client_id correspond
        if auth_code.client_id != client_id:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_grant", "error_description": "Authorization code was not issued to this client"}
            )
        
        # Vérifier si l'URI de redirection correspond
        if auth_code.redirect_uri != redirect_uri:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_grant", "error_description": "Invalid redirect URI"}
            )
        
        # Générer un jeton d'accès
        access_token = generate_token(48)
        refresh_token = generate_token(48)
        expires_in = TOKEN_EXPIRES_IN
        
        # Enregistrer le jeton
        tokens[access_token] = Token(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            scope=auth_code.scope,
            user_id=auth_code.user_id
        )
        
        # Supprimer le code d'autorisation
        del authorization_codes[code]
        
        # Retourner le jeton
        return JSONResponse(
            content={
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "scope": auth_code.scope
            }
        )
    
    # Point de terminaison d'enregistrement de client OAuth
    async def register_client(self, request: Request):
        # Cette méthode n'est pas implémentée dans cette version simplifiée
        return JSONResponse(
            status_code=501,
            content={"error": "not_implemented", "error_description": "Client registration is not implemented"}
        )
    
    # Récupère un client OAuth par son ID
    def _get_client(self, client_id):
        # Dans cette version simplifiée, nous utilisons un client de démonstration
        if client_id == demo_client.client_id:
            return demo_client
        return None
    
    # Récupère l'utilisateur actuel à partir de la session
    def _get_current_user(self, request: Request):
        session = request.session
        user_data = session.get("user")
        if not user_data:
            return None
        return User(**json.loads(user_data))
    
    # Vérifie si l'utilisateur a déjà autorisé un client
    def _has_user_authorized(self, user_id, client_id):
        user_auths = user_authorizations.get(user_id, [])
        return client_id in user_auths
    
    # Enregistre l'autorisation d'un utilisateur pour un client
    def _save_user_authorization(self, user_id, client_id):
        if user_id not in user_authorizations:
            user_authorizations[user_id] = []
        if client_id not in user_authorizations[user_id]:
            user_authorizations[user_id].append(client_id)
    
    # Affiche la page de connexion
    async def _render_login_page(self, request: Request):
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="templates")
        
        # Récupérer l'URI de redirection
        redirect_uri = request.query_params.get("redirect_uri", "/")
        
        # Récupérer le message d'erreur
        error = request.query_params.get("error", "")
        
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "redirect_uri": redirect_uri,
                "error": error
            }
        )
    
    # Affiche la page d'autorisation
    async def _render_authorization_page(self, request: Request, params, user):
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="templates")
        
        return templates.TemplateResponse(
            "authorize.html",
            {
                "request": request,
                "client": params["client"],
                "redirect_uri": params["redirect_uri"],
                "scope": params["scope"],
                "state": params["state"],
                "user": user
            }
        )
    
    # Authentifie un utilisateur à partir d'une requête
    async def _authenticate_user_from_request(self, request: Request):
        form_data = await request.form()
        
        # Récupérer les paramètres du formulaire
        email = form_data.get("email")
        password = form_data.get("password")
        redirect_uri = form_data.get("redirect_uri", "/")
        
        # Vérifier les paramètres requis
        if not email or not password:
            return RedirectResponse(url=f"/login?error=missing_credentials&redirect_uri={redirect_uri}")
        
        # Dans cette version simplifiée, nous acceptons n'importe quel email/mot de passe
        # Dans une application de production, vérifiez les informations d'identification dans une base de données
        
        # Créer un utilisateur
        user = User(
            email=email,
            user_id=generate_token(16)
        )
        
        # Enregistrer l'utilisateur dans la session
        request.session["user"] = json.dumps(user.dict())
        
        # Rediriger vers l'URI de redirection
        return RedirectResponse(url=redirect_uri)
    
    # Déconnecte un utilisateur
    async def _logout(self, request: Request):
        # Supprimer l'utilisateur de la session
        if "user" in request.session:
            del request.session["user"]
        
        # Rediriger vers la page d'accueil
        return RedirectResponse(url="/")

# Vérifie un jeton d'accès dans l'en-tête Authorization
def verify_token(request: Request):
    # Récupérer l'en-tête Authorization
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    
    # Vérifier le format de l'en-tête
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    # Récupérer le jeton
    token_str = parts[1]
    
    # Vérifier si le jeton existe
    token = tokens.get(token_str)
    if not token:
        return None
    
    # Vérifier si le jeton est expiré
    # Dans cette version simplifiée, nous ne vérifions pas l'expiration des jetons
    # Dans une application de production, vérifiez l'expiration des jetons
    
    return token

# Middleware pour protéger les routes avec authentification OAuth
def require_auth(request: Request = Depends()):
    token = verify_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Créer un utilisateur à partir du jeton
    user = User(
        email="user@example.com",  # Dans une application de production, récupérez l'email de l'utilisateur
        user_id=token.user_id
    )
    
    return user

# Initialiser un client de démonstration
demo_client = OAuthClient(
    client_id="demo-client",
    client_secret="demo-secret",
    client_name="Demo Client",
    redirect_uris=["http://localhost:8000/callback"],
    allowed_scopes=["profile", "email"]
)
