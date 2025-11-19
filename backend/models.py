from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from .database import Base


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)

    # Infos générales de la plateforme / AO
    plateforme = Column(String, index=True)
    reference = Column(String, index=True)
    acheteur = Column(String)
    titre = Column(String, index=True)
    type = Column(String)
    statut = Column(String)

    # Dates (format texte pour l’instant, conversion en datetime côté API si besoin)
    date_publication = Column(String, index=True)
    date_cloture = Column(String)
    fuseau_horaire = Column(String)

    # Catégorisation
    categories_unspsc = Column(String)
    # ✅ Nouvelle colonne : catégorie principale lisible (ex: "Services TI", "Cloud", etc.)
    categorie_principale = Column(String, nullable=True, index=True)

    # Budget
    budget = Column(Float, nullable=True)

    # Lien officiel
    lien = Column(String)

    # Mots-clés et extrait
    mots_cles_detectes = Column(String)
    # ✅ Nouvelle colonne : score de pertinence (0–100 par exemple)
    score_pertinence = Column(Float, nullable=True)
    extrait_recherche = Column(String)

    # Tag spécial (ex: AO pertinents ATS)
    est_ats = Column(Boolean, default=False)

    # Résumé de l’AO (texte libre)
    resume_ao = Column(String)

    # Localisation
    pays = Column(String, index=True)
    # ✅ Nouvelle colonne : région / province (ex: "QC", "ON")
    region = Column(String, index=True, nullable=True)
    portail = Column(String, index=True)

    # Lien vers la table des portails sources
    source_portal_id = Column(Integer, ForeignKey("source_portals.id"), nullable=True)
    source_portal = relationship("SourcePortal", back_populates="tenders")


class SourcePortal(Base):
    __tablename__ = "source_portals"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, unique=True, index=True)
    country = Column(String, index=True)
    level = Column(String)
    platform = Column(String)
    main_url = Column(String)
    api_official = Column(Boolean, default=False)
    api_url = Column(String)
    formats = Column(String)
    access_notes = Column(String)
    scraping_allowed = Column(String)
    recommended_method = Column(String)
    ti_keywords = Column(String)
    search_url = Column(String)
    pipeline_status = Column(String)

    tenders = relationship("Tender", back_populates="source_portal")


class KeywordProfile(Base):
    __tablename__ = "keyword_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    active = Column(Boolean, default=True)

    terms = relationship(
        "KeywordTerm",
        back_populates="profile",
        cascade="all, delete-orphan"
    )


class KeywordTerm(Base):
    __tablename__ = "keyword_terms"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("keyword_profiles.id"))
    term = Column(String, index=True)

    profile = relationship("KeywordProfile", back_populates="terms")
