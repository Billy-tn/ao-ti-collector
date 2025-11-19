# backend/pdf_tools.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, UploadFile, Depends
from pydantic import BaseModel

from . import auth

router = APIRouter(prefix="/tools", tags=["tools"])


class AoAnalysisResult(BaseModel):
    filename: str
    size_bytes: int
    summary: str
    main_requirements: list[str]
    risks: list[str]


@router.post("/analyze-ao", response_model=AoAnalysisResult)
async def analyze_ao(
    file: UploadFile = File(...),
    current_user: Optional[auth.AuthenticatedUser] = Depends(auth.get_current_user_optional),
) -> AoAnalysisResult:
    """
    Stub d'analyse IA : on ne lit pas vraiment le fichier, on renvoie juste
    un exemple structuré pour la démo.
    """
    content = await file.read()
    size = len(content)

    user_label = current_user.profile.full_name if current_user else "profil inconnu"

    return AoAnalysisResult(
        filename=file.filename,
        size_bytes=size,
        summary=(
            f"Analyse factice du document pour {user_label}. "
            "Le vrai moteur IA sera branché plus tard."
        ),
        main_requirements=[
            "Fournir une solution logicielle conforme aux normes de sécurité du secteur public",
            "Assurer la migration des données existantes sans interruption de service",
            "Prévoir un plan de formation pour les utilisateurs clés",
        ],
        risks=[
            "Sous-estimation de l'effort d'intégration avec les systèmes existants",
            "Dépendance à un fournisseur unique sans plan de sortie",
        ],
    )
