# backend/auth.py
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, status, Query
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

# En v4-dev-cursor on veut rester focus sur les boutons -> MFA OFF par défaut
MFA_ENABLED = os.getenv("AO_MFA_ENABLED", "false").lower() in ("1", "true", "yes", "y")


# ------------------------------------------------------------------
# Modèles
# ------------------------------------------------------------------

class TenderWin(BaseModel):
    ao_id: str
    title: str
    specialty: str
    date_awarded: str


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    activity_type: str
    main_specialty: str
    history: List[TenderWin]


class AuthenticatedUser(BaseModel):
    email: str
    profile: UserProfile


# ------------------------------------------------------------------
# Fake DB utilisateurs / tokens (in-memory)
# ------------------------------------------------------------------

FAKE_USERS: Dict[str, Dict[str, object]] = {
    "bilel@example.com": {
        "password": "password",
        "mfa_code": "123456",
        "profile": UserProfile(
            id="user-bilel",
            email="bilel@example.com",
            full_name="Bilel — Stratège AO TI",
            activity_type="Consultant TI / Intégrateur",
            main_specialty="Intégration ERP & IA",
            history=[
                TenderWin(ao_id="SEAO-001", title="Implantation Odoo pour PME", specialty="ERP Odoo", date_awarded="2023-05-10"),
                TenderWin(ao_id="SEAO-002", title="Modernisation ServiceNow ITSM", specialty="ITSM / ServiceNow", date_awarded="2024-02-18"),
                TenderWin(ao_id="SEAO-003", title="Plateforme AO Collector POC", specialty="Data & IA AO", date_awarded="2024-11-01"),
            ],
        ),
    },
    "cloud.consultant@example.com": {
        "password": "password",
        "mfa_code": "654321",
        "profile": UserProfile(
            id="user-cloud",
            email="cloud.consultant@example.com",
            full_name="Consultant Cloud & Sécurité",
            activity_type="Architecture cloud / DevSecOps",
            main_specialty="Cloud hybride & sécurité",
            history=[
                TenderWin(ao_id="SEAO-010", title="Migration Oracle vers cloud hybride", specialty="Cloud hybride & sécurité", date_awarded="2022-09-30"),
                TenderWin(ao_id="SEAO-011", title="Centre de services infonuagique", specialty="Cloud hybride & sécurité", date_awarded="2023-11-05"),
            ],
        ),
    },
    "odoo.partner@example.com": {
        "password": "password",
        "mfa_code": "999999",
        "profile": UserProfile(
            id="user-odoo",
            email="odoo.partner@example.com",
            full_name="Partenaire Odoo & Back-office",
            activity_type="Intégrateur ERP / Finance & RH",
            main_specialty="ERP Odoo finance & RH",
            history=[
                TenderWin(ao_id="SEAO-020", title="Implantation Odoo finance & RH", specialty="ERP Odoo finance & RH", date_awarded="2021-06-15"),
                TenderWin(ao_id="SEAO-021", title="Odoo pour la gestion de projets publics", specialty="ERP Odoo finance & RH", date_awarded="2024-04-03"),
            ],
        ),
    },
}

TEMP_TOKENS: Dict[str, str] = {}  # temp_token -> email
ACCESS_TOKENS: Dict[str, Dict[str, object]] = {}  # access_token -> { email, created_at }


def _create_temp_token(email: str) -> str:
    token = f"tmp_{uuid.uuid4().hex}"
    TEMP_TOKENS[token] = email
    return token


def _create_access_token(email: str) -> str:
    token = f"acc_{uuid.uuid4().hex}"
    ACCESS_TOKENS[token] = {"email": email, "created_at": datetime.utcnow().isoformat()}
    return token


# ------------------------------------------------------------------
# Schémas API
# ------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    message: str
    mfa_required: bool
    temp_token: Optional[str] = None
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserProfile] = None


class VerifyMfaRequest(BaseModel):
    temp_token: str
    code: str


class VerifyMfaResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


# ------------------------------------------------------------------
# Routes auth
# ------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    email = payload.email.strip().lower()
    password = payload.password

    if email not in FAKE_USERS:
        raise HTTPException(status_code=401, detail="Utilisateur inconnu")

    user_entry = FAKE_USERS[email]
    if password != user_entry["password"]:
        raise HTTPException(status_code=401, detail="Mot de passe invalide")

    profile: UserProfile = user_entry["profile"]  # type: ignore

    # MFA OFF -> on donne direct un access token
    if not MFA_ENABLED:
        access_token = _create_access_token(email)
        return LoginResponse(
            message="Connexion réussie (MFA désactivé).",
            mfa_required=False,
            access_token=access_token,
            user=profile,
        )

    # MFA ON -> temp token
    temp_token = _create_temp_token(email)
    return LoginResponse(
        message="Code MFA envoyé (factice). Utilisez le code affiché à l'écran.",
        mfa_required=True,
        temp_token=temp_token,
        access_token=None,
        user=None,
    )


@router.post("/verify-mfa", response_model=VerifyMfaResponse)
def verify_mfa(payload: VerifyMfaRequest) -> VerifyMfaResponse:
    if payload.temp_token not in TEMP_TOKENS:
        raise HTTPException(status_code=401, detail="Token temporaire invalide ou expiré")

    email = TEMP_TOKENS.pop(payload.temp_token)
    user_entry = FAKE_USERS[email]

    if payload.code != user_entry["mfa_code"]:
        raise HTTPException(status_code=401, detail="Code MFA invalide")

    access_token = _create_access_token(email)
    profile: UserProfile = user_entry["profile"]  # type: ignore

    return VerifyMfaResponse(access_token=access_token, user=profile)


# ------------------------------------------------------------------
# Dépendances FastAPI
# ------------------------------------------------------------------

def _extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Format d'auth invalide")
    return parts[1]


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None, description="Dev-only fallback: pass access token as ?token=... when headers are not possible."),
) -> AuthenticatedUser:
    # If no Authorization header (e.g., direct link download), allow ?token=... as a fallback.
    if not authorization and token:
        authorization = f"Bearer {token}"
    token = _extract_token(authorization)
    token_info = ACCESS_TOKENS.get(token)
    if not token_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide ou expiré")

    email = str(token_info["email"])
    user_entry = FAKE_USERS.get(email)
    if not user_entry:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")

    return AuthenticatedUser(email=email, profile=user_entry["profile"])  # type: ignore


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> Optional[AuthenticatedUser]:
    if not authorization and not token:
        return None
    try:
        return get_current_user(authorization=authorization, token=token)
    except HTTPException:
        return None

# === AO_AUTH_DISABLED BYPASS (AUTO) ===
import os as _os
import asyncio as _asyncio

def _dev_user():
    # user dev minimal
    return {"id":"dev","email":"dev@local","full_name":"Dev User"}

# capture une éventuelle implémentation existante/importée
try:
    _REAL_GET_CURRENT_USER = get_current_user  # type: ignore[name-defined]
except Exception:
    _REAL_GET_CURRENT_USER = None

async def get_current_user(*args, **kwargs):  # noqa: F811
    """DEV: bypass auth/MFA si AO_AUTH_DISABLED=1 (par défaut)."""
    if _os.getenv("AO_AUTH_DISABLED", "1") == "1":
        return _dev_user()

    if _REAL_GET_CURRENT_USER is None:
        raise RuntimeError("Auth activée (AO_AUTH_DISABLED=0) mais pas de get_current_user réel trouvé.")

    # supporter sync ou async
    if _asyncio.iscoroutinefunction(_REAL_GET_CURRENT_USER):
        return await _REAL_GET_CURRENT_USER(*args, **kwargs)
    return _REAL_GET_CURRENT_USER(*args, **kwargs)

# === AO_AUTH_DISABLED BYPASS FIX (AUTO) ===
from typing import Optional as _Optional
from fastapi import Header as _Header
import os as _os2

def _bypass_user_safe():
    try:
        # on privilégie l'admin fake si présent
        if "admin@example.com" in FAKE_USERS:
            email = "admin@example.com"
        else:
            email = next(iter(FAKE_USERS.keys()))
        prof = FAKE_USERS[email]["profile"]
        return AuthenticatedUser(email=email, profile=prof)  # type: ignore
    except Exception:
        # fallback minimal
        return AuthenticatedUser(
            email="dev@local",
            profile=UserProfile(
                id="dev",
                email="dev@local",
                full_name="Dev User",
                activity_type="dev",
                main_specialty="IT",
                history=[],
            ),
        )

def get_current_user(authorization: _Optional[str] = _Header(default=None)) -> AuthenticatedUser:
    # bypass complet (dev)
    if _os2.getenv("AO_AUTH_DISABLED", "0").lower() in ("1", "true", "yes", "y"):
        return _bypass_user_safe()

    # sinon -> on retombe sur l'implémentation originale (si elle existe)
    try:
        return _REAL_GET_CURRENT_USER(authorization=authorization)  # type: ignore
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth non disponible")
