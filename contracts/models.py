"""BOUSSOLA — contrats d'entrée/sortie. SOURCE DE VÉRITÉ UNIQUE.

Les schémas JSON de `contracts/*.schema.json` sont GÉNÉRÉS depuis ce fichier
(`make contracts`). Ne jamais éditer les .json à la main : ils dériveraient.

Le contrat de sortie `Diagnosis` reprend exactement les champs demandés par le
cahier des charges BNA : identifiant du dossier, étape, statut, cause,
explication client et agent, sources citées, actions autorisées, indicateur de
validation humaine obligatoire, niveau de confiance, traçabilité.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Énumérations du parcours H24
# --------------------------------------------------------------------------


class Step(str, Enum):
    ORIENTATION = "ORIENTATION"
    CHOIX_AGENCE = "CHOIX_AGENCE"
    IDENTITE = "IDENTITE"
    COORDONNEES = "COORDONNEES"
    PROFIL = "PROFIL"
    CHOIX_OFFRE = "CHOIX_OFFRE"
    DOCUMENTS = "DOCUMENTS"
    SIGNATURE = "SIGNATURE"
    VALIDATION_AGENCE = "VALIDATION_AGENCE"
    ACTIVATION = "ACTIVATION"


class Status(str, Enum):
    EN_COURS = "EN_COURS"
    EN_ATTENTE = "EN_ATTENTE"
    BLOQUE = "BLOQUE"
    REJETE = "REJETE"
    ACTIVE = "ACTIVE"


class Residence(str, Enum):
    RESIDENT = "resident"
    NON_RESIDENT = "non_resident"


class StatutPro(str, Enum):
    ETUDIANT = "etudiant"
    SALARIE = "salarie"
    PROFESSION_LIBERALE = "profession_liberale"
    RETRAITE = "retraite"
    SANS_EMPLOI = "sans_emploi"


class DocType(str, Enum):
    CIN = "CIN"
    PASSEPORT = "PASSEPORT"
    CARTE_SEJOUR = "CARTE_SEJOUR"
    JUSTIFICATIF_DOMICILE = "JUSTIFICATIF_DOMICILE"
    FICHE_PAIE = "FICHE_PAIE"
    CARTE_ETUDIANT = "CARTE_ETUDIANT"
    ATTESTATION_TRAVAIL = "ATTESTATION_TRAVAIL"
    RIB_EXTERNE = "RIB_EXTERNE"
    SPECIMEN_SIGNATURE = "SPECIMEN_SIGNATURE"


class DocStatut(str, Enum):
    FOURNI = "fourni"
    MANQUANT = "manquant"
    ILLISIBLE = "illisible"
    EXPIRE = "expire"


class Owner(str, Enum):
    CLIENT = "client"
    AGENCE = "agence"
    BACK_OFFICE = "back_office"
    SECURITE = "securite"


class Trust(str, Enum):
    """Niveau de confiance d'un contenu injecté dans le prompt.

    `CORPUS` = documentation BNA versionnée, autorisée à porter des règles.
    `UNTRUSTED` = tout contenu d'origine externe (OCR, texte libre client,
    notes back-office). Ne porte JAMAIS d'instruction exécutable.
    """

    CORPUS = "corpus"
    UNTRUSTED = "untrusted"


# --------------------------------------------------------------------------
# Dossier (entrée)
# --------------------------------------------------------------------------


class Prospect(BaseModel):
    prospect_id: str
    nom: str
    prenom: str
    date_naissance: str  # ISO date
    nationalite: str
    residence: Residence
    statut_pro: StatutPro
    revenu_mensuel_declare: int | None = None
    telephone: str
    email: str
    cin: str | None = None
    passeport: str | None = None


class Document(BaseModel):
    doc_id: str
    type: DocType
    statut: DocStatut
    depose_at: str | None = None
    emis_le: str | None = None
    expire_le: str | None = Field(
        default=None, description="Date d'expiration — pièces d'identité uniquement."
    )
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ocr_text: str | None = Field(
        default=None,
        description="CONTENU NON FIABLE. Toujours encapsulé en Trust.UNTRUSTED.",
    )


class OtpState(BaseModel):
    tentatives: int = 0
    max_tentatives: int = 3
    dernier_envoi_at: str | None = None
    canal: Literal["sms", "email"] = "sms"
    dernier_code_statut: Literal["ok", "echec", "expire", "non_envoye"] = "non_envoye"


class SignatureState(BaseModel):
    statut: Literal["non_requise", "en_attente", "signee", "echec"] = "non_requise"
    signed_at: str | None = None


class AgenceState(BaseModel):
    code_agence: str | None = None
    en_file_depuis: str | None = None
    sla_heures: int = 48
    rdv_at: str | None = None
    rdv_honore: bool | None = None


class Offre(BaseModel):
    pack_code: str
    pack_label: str


class Event(BaseModel):
    at: str
    source: Literal["H24", "CSA", "OCR", "CLIENT"]
    type: str
    detail: str


class Dossier(BaseModel):
    """État d'un dossier tel qu'exposé par l'API parcours H24 (synthétique)."""

    dossier_id: str
    created_at: str
    updated_at: str
    canal: Literal["web", "mobile"] = "web"
    step: Step
    status: Status
    error_code: str | None = None
    error_message: str | None = Field(
        default=None, description="Message générique affiché au client — souvent inexploitable."
    )
    prospect: Prospect
    offre: Offre | None = None
    documents: list[Document] = []
    otp: OtpState = OtpState()
    signature: SignatureState = SignatureState()
    agence: AgenceState = AgenceState()
    events: list[Event] = []
    message_client: str | None = Field(
        default=None, description="Texte libre saisi par le client. CONTENU NON FIABLE."
    )


# --------------------------------------------------------------------------
# Diagnostic (sortie)
# --------------------------------------------------------------------------


class Evidence(BaseModel):
    """Un fait typé, extrait de manière déterministe, qui soutient une cause."""

    fact: str = Field(description="Identifiant du fait, ex. 'doc.cin.expire'")
    value: Any = None
    weight: float = Field(description="Contribution au score de la cause")
    source: str = Field(description="D'où vient le fait : h24, csa, ocr, calcul")


class Citation(BaseModel):
    anchor: str = Field(description="Ancre de règle stable, ex. 'R-IDN-003'")
    doc_id: str
    titre: str
    extrait: str
    version: str


class CauseCandidate(BaseModel):
    cause_id: str = Field(description="OBLIGATOIREMENT un id de contracts/causes.yaml")
    family: str
    label_fr: str
    confidence: float = Field(ge=0.0, le=1.0)
    owner: Owner
    evidence: list[Evidence] = []
    anchors: list[str] = []


class UnblockStep(BaseModel):
    order: int
    action: str
    owner: Owner
    eta_hours: int
    anchors: list[str] = []


class ExplanationClient(BaseModel):
    fr: str
    ar: str | None = None
    en: str | None = None
    traduction: Literal["modele", "gabarit"] | None = Field(
        default=None, description="« gabarit » : texte pré-écrit (étape + libellé de cause), détail des actions en français.")


class ExplanationAgent(BaseModel):
    summary: str
    suggested_message: str = Field(description="Formulation prête à transmettre au client")
    escalation_draft: str | None = None


class PolicyDecision(BaseModel):
    rule: str
    triggered: bool
    detail: str


class ToolCallRecord(BaseModel):
    seq: int
    tool: str
    args_digest: str
    allowed: bool
    reason: str | None = None
    latency_ms: int | None = None


class Trace(BaseModel):
    """Boîte de verre : tout ce qu'il faut pour rejouer et auditer la réponse.

    N'expose jamais le prompt système ni le raisonnement brut du modèle —
    uniquement des faits, des scores et des décisions de politique.
    """

    facts: list[Evidence] = []
    graph_scores: dict[str, float] = {}
    retrieved_anchors: list[str] = []
    tool_calls: list[ToolCallRecord] = []
    policy_decisions: list[PolicyDecision] = []
    adjudicated: bool = False
    adjudication_reason: str | None = None
    groundedness_score: float | None = None
    audit_chain_head: str | None = None
    latency_ms: int | None = None
    provider: str | None = None
    cost_usd: float | None = None


class Diagnosis(BaseModel):
    """Contrat de sortie. Rendu identique pour le client et pour l'agent."""

    trace_id: str
    dossier_id: str
    step: Step
    status: Status
    error_code: str | None = None
    causes: list[CauseCandidate] = Field(description="Triées par confiance décroissante")
    unblock_path: list[UnblockStep] = []
    explanation_client: ExplanationClient
    explanation_agent: ExplanationAgent
    sources: list[Citation] = []
    allowed_actions: list[str] = []
    human_validation_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool = False
    trace: Trace

    @property
    def top_cause(self) -> str:
        return self.causes[0].cause_id if self.causes else "C-UNK-000"


class DiagnoseRequest(BaseModel):
    dossier_id: str
    question: str | None = Field(
        default=None, description="Question libre du client ou de l'agent. CONTENU NON FIABLE."
    )
    audience: Literal["client", "agent"] = "client"
    locale: Literal["fr", "ar", "en"] = "fr"
