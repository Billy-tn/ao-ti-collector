from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from . import auth

router = APIRouter(tags=["ai"])


@router.post("/ai/analyze")
async def analyze_ao(
    tender_id: Optional[int] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    files: List[UploadFile] = File(...),
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
) -> Dict[str, Any]:
    """
    Endpoint protégé: analyse IA d'un AO à partir de documents téléversés.
    (Pour l’instant: mock/stub -> renvoie un résultat simulé.)
    """
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier reçu.")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Max 10 fichiers par analyse.")

    # Contrôle taille: on lit en streaming avec plafond (10MB par fichier)
    max_bytes = 10 * 1024 * 1024
    file_infos = []
    for f in files:
        size = 0
        while True:
            chunk = await f.read(1024 * 1024)  # 1MB
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"Fichier trop gros: {f.filename} (>10MB)",
                )

        # reset pour usage futur éventuel
        try:
            f.file.seek(0)
        except Exception:
            pass

        file_infos.append(
            {
                "filename": f.filename,
                "content_type": f.content_type,
                "size_bytes": size,
            }
        )

    analysis_id = f"ana_{uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat() + "Z"

    # Résultat mock (le vrai agent IA viendra ensuite)
    result = {
        "summary": "Analyse IA (mock): documents reçus, extraction à venir.",
        "extracted_fields": {
            "tender_id": tender_id,
            "closing_date": None,
            "buyer": None,
            "estimated_value": None,
        },
        "next_actions": [
            "Identifier les exigences obligatoires",
            "Extraire les dates clés (clôture / visite / questions)",
            "Lister les livrables + critères d’évaluation",
        ],
        "confidence": 0.25,
    }

    return {
        "status": "ok",
        "analysis_id": analysis_id,
        "created_at": now,
        "inputs": {
            "tender_id": tender_id,
            "notes": notes,
            "file_count": len(file_infos),
            "files": file_infos,
        },
        "result": result,
        "user": current_user.profile.dict(),
    }
