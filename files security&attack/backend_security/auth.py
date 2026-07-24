"""
auth.py — CocoaSecure IoT API
Authentification JWT + contrôle d'accès basé sur les rôles (RBAC).

Rôles définis (conformes à la matrice STRIDE — contre-mesure "Elevation of Privilege") :
- viewer   : lecture seule des dashboards et lectures
- operator : + accès aux alertes détaillées, export de données
- admin    : + gestion des utilisateurs, accès complet

Stockage des utilisateurs : collection MongoDB "users" (mot de passe hashé bcrypt,
jamais en clair). Voir seed_users.py pour créer les comptes initiaux.
"""

import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from pymongo.collection import Collection

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
# IMPORTANT : en production, définir SECRET_KEY via variable d'environnement
# (.env, jamais commit sur Git). Valeur ci-dessous = fallback pour le dev local.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_MOI_EN_PRODUCTION_cle_secrete_longue_aleatoire")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Role(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


# Hiérarchie des rôles : un admin peut tout faire, un operator peut faire
# ce qu'un viewer peut faire, etc.
ROLE_HIERARCHY = {
    Role.VIEWER: 0,
    Role.OPERATOR: 1,
    Role.ADMIN: 2,
}


class TokenData(BaseModel):
    username: str
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


class UserOut(BaseModel):
    username: str
    role: Role
    site: Optional[str] = None  # ex: responsable d'une coopérative précise


# ─────────────────────────────────────────────────────────────
# Hachage de mot de passe
# ─────────────────────────────────────────────────────────────
def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ─────────────────────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────────────────────
def create_access_token(username: str, role: Role) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        return TokenData(username=username, role=Role(role))
    except JWTError:
        raise credentials_exception


# ─────────────────────────────────────────────────────────────
# Authentification contre MongoDB
# ─────────────────────────────────────────────────────────────
def authenticate_user(users_collection: Collection, username: str, password: str) -> Optional[dict]:
    user = users_collection.find_one({"username": username})
    if not user:
        return None
    if not verify_password(password, user["hashedPassword"]):
        return None
    return user


# ─────────────────────────────────────────────────────────────
# Dépendances FastAPI — à utiliser dans les routes protégées
# ─────────────────────────────────────────────────────────────
def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return decode_access_token(token)


def require_role(minimum_role: Role):
    """
    Dépendance générique : exige un rôle minimum (hiérarchique).
    Exemple : Depends(require_role(Role.OPERATOR)) autorise operator ET admin.
    """
    def dependency(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if ROLE_HIERARCHY[current_user.role] < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé — rôle '{minimum_role.value}' minimum requis "
                       f"(rôle actuel : '{current_user.role.value}')",
            )
        return current_user
    return dependency


# Raccourcis pratiques pour les routes
require_viewer = require_role(Role.VIEWER)
require_operator = require_role(Role.OPERATOR)
require_admin = require_role(Role.ADMIN)
