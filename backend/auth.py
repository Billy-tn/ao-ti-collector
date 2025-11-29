# backend/auth.py
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, status
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


def get_current_user(authorization: Optional[str] = Header(default=None)) -> AuthenticatedUser:
    token = _extract_token(authorization)
    token_info = ACCESS_TOKENS.get(token)
    if not token_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide ou expiré")

    email = str(token_info["email"])
    user_entry = FAKE_USERS.get(email)
    if not user_entry:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")

    return AuthenticatedUser(email=email, profile=user_entry["profile"])  # type: ignore


def get_current_user_optional(authorization: Optional[str] = Header(default=None)) -> Optional[AuthenticatedUser]:
    if not authorization:
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None
