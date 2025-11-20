# backend/pdf_tools.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import JSONResponse

from . import auth

router = APIRouter(tags=["ao-pdf", "documents"])


@router.post("/ao/analyse-pdf")
async def analyse_ao_pdf(
    file: UploadFile = File(...),
    current_user: auth.UserProfile = Depends(auth.get_current_user),
):
    """
    Téléversement d'un PDF d'AO (téléchargé depuis SEAO / CanadaBuys).
    Pour l'instant : stub → on retourne juste des infos de base.
    Plus tard : on branchera l'IA ici.
    """
    content = await file.read()
    size_bytes = len(content)

    return JSONResponse(
        {
            "status": "ok",
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": size_bytes,
            "message": (
                "PDF reçu. Analyse IA à brancher (stub backend). "
                "Tu peux déjà afficher ce résultat dans l'IHM."
            ),
        }
    )


@router.post("/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: auth.UserProfile = Depends(auth.get_current_user),
):
    """
    Téléversement générique de documents (.pdf, .docx, .xlsx, etc.).
    Pour l'instant : on ne stocke rien, on retourne juste un résumé.
    """
    infos = []
    total_size = 0

    for f in files:
        data = await f.read()
        size = len(data)
        total_size += size
        infos.append(
            {
                "filename": f.filename,
                "content_type": f.content_type,
                "size_bytes": size,
            }
        )

    return JSONResponse(
        {
            "status": "ok",
            "count": len(files),
            "total_size_bytes": total_size,
            "files": infos,
            "message": (
                "Documents reçus. Traitement IA / indexation à brancher plus tard."
            ),
        }
    )
