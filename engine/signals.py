"""BOUSSOLA — étage A : extraction de faits typés.

Aucun modèle de langage ici. Que des prédicats Python sur l'état du dossier et
sur ce que les outils ont renvoyé. C'est ce qui rend le diagnostic rejouable :
mêmes entrées, mêmes faits, mêmes scores.

Convention de nommage des faits : `<domaine>.<predicat>`, domaines alignés sur
les familles de causes (ori, ident, otp, doc, prof, offre, dup, agc, syn, sec).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from contracts.models import Dossier

# Durées de référence, adossées au corpus.
JOURS_VALIDITE_JUSTIF_DOMICILE = 90     # R-DOC-003 : trois mois
SEUIL_OCR_LISIBLE = 0.70                # R-DOC-004
SEUIL_REVENU_JUSTIFICATIF = 500         # R-PRF-002
JOURS_INACTIVITE_EXPIRATION = 30        # R-GEN-003
MINUTES_VERROU_OTP = 30                 # R-OTP-003
MINUTES_ECART_ADMISSIBLE = 15           # R-SYN-002
AGE_MINIMUM = 18                        # R-IDN-005

PIECES_IDENTITE = {"CIN", "PASSEPORT", "CARTE_SEJOUR"}
JUSTIFICATIFS_REVENU = {
    "salarie": {"FICHE_PAIE", "ATTESTATION_TRAVAIL"},
    "retraite": {"ATTESTATION_TRAVAIL"},
    "profession_liberale": {"ATTESTATION_TRAVAIL"},
    "etudiant": set(),
    "sans_emploi": set(),
}
SOCLE_HORS_IDENTITE = {"JUSTIFICATIF_DOMICILE", "SPECIMEN_SIGNATURE"}   # R-DOC-001

# Motifs d'injection. Volontairement sur du texte normalisé (sans accents, en
# minuscules) pour résister aux variantes d'écriture les plus simples.
MOTIFS_INJECTION = [
    # --- contournement explicite des consignes (fr / en) ---
    (r"ignore[rz]?\s+(tes|les|vos|toutes?|mes)\s+(consignes|instructions|regles)", "override_consignes"),
    (r"oubli[e|ez]\s+(tes|les|vos)\s+(consignes|instructions)", "override_consignes"),
    (r"(ignore|disregard|forget)\s+(all\s+)?(your\s+)?(previous|prior|above)\s+(instructions|rules|prompts)", "override_consignes_en"),
    (r"\bتجاهل\s+(كل\s+)?(التعليمات|الاوامر|التعليمة)", "override_consignes_ar"),
    (r"(passer?|passe[rz]?)\s+outre", "demande_contournement"),
    (r"contourner?\s+(la\s+)?(verification|regle|controle|procedure)", "demande_contournement"),
    (r"desactive[rz]?\s+(temporairement\s+)?(tes|les|vos)\s+(garde-?fous|restrictions|controles|securites)", "demande_contournement"),
    (r"(mode|sans)\s+(sans\s+)?restriction", "demande_contournement"),
    (r"mode\s+(developpeur|debug|admin)", "demande_contournement"),
    (r"n'?escalade\s+pas", "demande_contournement"),
    (r"sans\s+(aucun\s+)?controle", "demande_contournement"),

    # --- usurpation de rôle / d'autorité ---
    (r"\b(system|systeme)\s*:", "faux_role_systeme"),
    (r"note\s+pour\s+le\s+systeme", "faux_role_systeme"),
    (r"instruction\s+(administrateur|admin|officielle)", "faux_role_systeme"),
    (r"tu\s+es\s+(maintenant|desormais)\s+(l'|le\s+)?(administrateur|admin|superviseur|directeur)", "usurpation_role"),
    (r"you\s+are\s+now\s+(the\s+)?(admin|administrator|supervisor)", "usurpation_role_en"),
    (r"\bانت\s+الان\s+(المدير|المسؤول)", "usurpation_role_ar"),
    (r"je\s+(suis|t'autorise)\s+.{0,40}(directeur|auditeur|dsi|responsable)", "usurpation_role"),
    (r"(je\s+)?t'autorise\s+a", "usurpation_role"),
    (r"en\s+tant\s+qu'?\s*(auditeur|administrateur|agent\s+bna|employe)", "usurpation_role"),
    (r"(test|controle)\s+officiel\s+de\s+la\s+(dsi|direction)", "usurpation_role"),
    (r"m'?autorise\s+a\s+contourner", "usurpation_role"),

    # --- demande de décision bancaire (le cœur du garde-fou R-SEC-002) ---
    # --- paraphrases du contournement (niveau 1) ---
    (r"fais?\s+comme\s+si\s+(les\s+)?(regles|consignes|instructions|limites)", "override_consignes"),
    (r"laisse[rz]?\s+(de\s+cote|tomber)\s+(tes|les|vos)\s+(limites|regles|consignes|restrictions)", "override_consignes"),
    (r"(ignore|disregard|forget|oublie)[a-z]*\s+(les\s+|tes\s+|the\s+|all\s+|your\s+)*(controles|verifications|guidelines|previous\s+guidelines)", "override_consignes"),
    (r"ne\s+verifie\s+rien|ne\s+controle\s+rien|sauter\s+la\s+verification|skip\s+(the\s+)?(kyc|check|verification|controls?)", "demande_contournement"),
    (r"pretend\s+(you|that|to)", "override_consignes_en"),
    (r"(developer|debug|maintenance)\s+mode|mode\s+maintenance", "demande_contournement"),
    (r"you\s+are\s+in\s+(developer|admin)", "usurpation_role_en"),
    (r"tu\s+es\s+autorise\s+a|ici\s+(le|la)\s+(directeur|directrice|responsable|dsi)|message\s+du\s+service\s+informatique", "usurpation_role"),
    (r"je\s+suis\s+(un\s+)?(agent|conseiller|employe)\s+(de\s+la\s+)?bna", "usurpation_role"),
    # --- extraction de la configuration ---
    (r"(instructions|consignes)\s+(que\s+tu\s+as\s+recues|recues|initiales)", "exfiltration_consignes"),
    (r"message\s+de\s+configuration|texte\s+exact\s+de\s+ton", "exfiltration_consignes"),
    (r"(what\s+is|what\s+are|print|show)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions)|print\s+it\s+verbatim", "exfiltration_consignes_en"),
    # --- arabe, dialecte tunisien, arabizi ---
    (r"تجاهل\s+(كل\s+)?(ال)?(قواعد|تعليمات|اوامر|قوانين)", "override_consignes_ar"),
    (r"(اعطيني|قولي|اكشف|اظهر)\s+(لي\s+)?(ال)?(تعليمات|قواعد)", "exfiltration_consignes_ar"),
    (r"(نتخطى|تخطى|نتجاوز|تجاوز)\s+(ال)?(تحقق|هويه|اجراءات|مراقبه)|خلي\s+الملف\s+يعدي", "demande_contournement_ar"),
    (r"\bma\s+t?verifi(ch)?\b|\bnsa\s+(el\s+)?(regles|consignes|instructions)", "demande_contournement"),

    (r"valide[rz]?\s+(automatiquement|immediatement|sans\s+controle)", "demande_validation_auto"),
    (r"\bفعّ?ل\s+(حسابي|اشتراكي)", "demande_activation_ar"),
    (r"considerer?\s+.{0,40}comme\s+conforme", "demande_validation_auto"),
    (r"accorde[rz]?\s+(moi\s+)?(une\s+)?derogation", "demande_derogation"),
    (r"(supprime|efface)[rz]?\s+(le\s+)?dossier", "demande_modification"),
    (r"change[rz]?\s+mon\s+statut", "demande_modification"),
    (r"fai(s|re)\s+une\s+exception", "demande_derogation"),
    (r"validé?\s+d'?office", "demande_validation_auto"),

    # --- extraction des consignes internes ---
    (r"(repete|affiche|donne|montre)[a-z]*[-\s]+(moi\s+)?(ton|le|tes|les)\s+(prompt|invite|consignes|instructions|outils|regles)", "exfiltration_consignes"),
    (r"liste\s+(complete\s+)?de\s+tes\s+outils", "exfiltration_consignes"),
    (r"(prompt|invite)\s+(systeme|system)", "exfiltration_consignes"),
    (r"seuil\s+de\s+confiance", "exfiltration_consignes"),
    (r"(graph|contracts?)\.?ya?ml", "exfiltration_consignes"),

    # --- déguisements ---
    (r"<!--", "balise_masquee"),
    (r"traduis\s+puis\s+execute", "consigne_indirecte"),
    (r"execute\s+(ceci|cela|la\s+phrase)", "consigne_indirecte"),
]
MOTIFS_HORS_PERIMETRE = [
    (r"\bDOS-[A-Z]{3}-\d{6}\b", "autre_dossier_designe"),
    (r"(liste|tous les|toutes les)\s+(clients|dossiers|titulaires)", "demande_liste_clients"),
    (r"(numero de telephone|telephone|cin|adresse)\s+(de|du)\s+(son|la|le)\s+titulaire", "pii_tiers"),
    (r"avec\s+(leurs|les)\s+(cin|noms|numeros)", "pii_tiers"),
    (r"noms?\s+des\s+titulaires", "pii_tiers"),
    (r"(coordonnees|donnees|dossiers?|numeros?|adresses?)\s+(des|d')\s*(autres|tiers)|autres\s+(personnes|clients|titulaires|prospects|applicants)", "pii_tiers"),
    (r"cin\s+du\s+titulaire|other\s+applicants", "pii_tiers"),
]


# Niveau 2 — une demande de décision n'est une manipulation que si elle cherche à CONTOURNER (marqueur dur) ou
# à presser (marqueur doux, hors question polie). « Pouvez-vous valider mon dossier ? » est une demande légitime
# d'un client : l'assistant n'en décide pas, il explique ce qui manque — il ne la traite pas en attaque.
VERBES_DECISION = (r"\b(valide|valider|validez|approuve|approuver|approuvez|active|activer|activez|debloque|debloquer|"
                   r"debloquez|ouvre|ouvrir|passe|autorise|certifie|approve|activate|validate|unlock|authori[sz]e|mark|"
                   r"mets)\b")
MARQUEURS_DURS = [r"sans\s+(aucun\s+)?(controle|verification|condition|attendre)", r"automatiquement|d'office|a\s+ma\s+place",
                  r"ne\s+(verifie|controle)\s+rien", r"without\s+(any\s+)?(check|verification|waiting)", r"\bbila\b|\bbla\b",
                  r"porte\s+plainte|sous\s+peine|je\s+prends\s+la\s+responsabilite|c'est\s+ordonne|ne\s+veux\s+pas\s+attendre",
                  r"contourne|bypass|(procedure|regle)s?\s+habituelle", r"à\s+partir\s+de\s+maintenant|a\s+partir\s+de\s+maintenant"]
MARQUEURS_DOUX = [r"tout\s+de\s+suite|immediatement|directement|maintenant|tawa|right\s+away|\bnow\b|aujourd'hui"]
QUESTION_POLIE = r"pouvez-vous|pourriez-vous|peut-on|est-ce\s+que|serait-il\s+possible|could\s+you|can\s+you|quand\s+|comment\s+"


def _decision_sous_pression(texte_norm: str, *, doux: bool = True) -> bool:
    if not re.search(VERBES_DECISION, texte_norm):
        return False
    if any(re.search(m, texte_norm) for m in MARQUEURS_DURS):
        return True
    return doux and not re.search(QUESTION_POLIE, texte_norm) and any(re.search(m, texte_norm) for m in MARQUEURS_DOUX)


def _norm(txt: str) -> str:
    """Minuscules, sans diacritiques, sans espacement parasite.

    La détection ne doit dépendre ni de l'orthographe, ni de la casse, ni des
    astuces d'écriture les plus courantes (« i g n o r e », « ignoré »). Les
    harakat arabes tombent aussi, puisqu'elles sont des marques combinantes.
    """
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c)).lower()
    # Arabe : variantes d'alef, ya, ta marbuta et tatweel ramenées à une forme (sinon « أ » ≠ « ا »).
    txt = txt.translate({0x623: "ا", 0x625: "ا", 0x622: "ا", 0x649: "ي", 0x629: "ه", 0x640: None})
    # « i g n o r e t e s » -> « ignore tes » : on recolle les suites de
    # lettres isolées, technique d'évasion la plus répandue.
    txt = re.sub(r"\b(?:[a-z] ){2,}[a-z]\b", lambda m: m.group(0).replace(" ", ""), txt)
    return re.sub(r"\s+", " ", txt)


@dataclass
class Fact:
    name: str
    value: Any
    source: str


@dataclass
class WorldView:
    """Ce que les outils ont réellement renvoyé pour CETTE session.

    Rempli uniquement par le courtier (engine/broker.py) : si un appel a été
    refusé, le champ reste vide et le diagnostic en tient compte au lieu de
    supposer.
    """

    relations: list[dict] = field(default_factory=list)
    subscriptions: list[dict] = field(default_factory=list)
    doublons: list[dict] = field(default_factory=list)
    etat_csa: dict | None = None
    agency_queue: dict | None = None
    question: str | None = None
    injection_llm: dict | None = None   # verdict du classifieur (engine/quarantine.py)


def _age(naissance: str, as_of: date) -> int:
    n = date.fromisoformat(naissance)
    return as_of.year - n.year - ((as_of.month, as_of.day) < (n.month, n.day))


def _parse_ocr_identite(txt: str) -> dict[str, str]:
    out = {}
    for cle, motif in [("nom", r"NOM\s*:\s*(.+)"), ("prenom", r"PRENOM\s*:\s*(.+)"),
                       ("naissance", r"NE\(?E?\)?\s+LE\s*:\s*(.+)")]:
        m = re.search(motif, txt or "", re.I)
        if m:
            out[cle] = m.group(1).strip()
    return out


def _jours(depuis: str | None, as_of: date) -> int | None:
    if not depuis:
        return None
    return (as_of - date.fromisoformat(depuis[:10])).days


def _heures(depuis: str | None, now: datetime) -> float | None:
    if not depuis:
        return None
    return (now - datetime.fromisoformat(depuis)).total_seconds() / 3600


def extract(dossier: Dossier, world: WorldView, *, catalog: dict,
            as_of: datetime) -> dict[str, Fact]:
    """Produit l'ensemble des faits du dossier. Déterministe et sans effet de bord."""
    today = as_of.date()
    f: dict[str, Fact] = {}

    def put(name: str, value: Any, source: str) -> None:
        f[name] = Fact(name, value, source)

    p = dossier.prospect
    docs = dossier.documents
    fournis = [d for d in docs if d.statut.value in ("fourni", "illisible", "expire")]
    par_type = {d.type.value: d for d in fournis}
    packs = {x["pack_code"]: x for x in catalog["packs"]}
    pack = packs.get(dossier.offre.pack_code) if dossier.offre else None

    # --- pseudo-faits utilisés par les conditions du graphe --------------
    put("step", dossier.step.value, "h24")
    put("status", dossier.status.value, "h24")
    put("error_code", dossier.error_code, "h24")
    put("prospect.non_resident", p.residence.value == "non_resident", "h24")
    age = _age(p.date_naissance, today)
    put("prospect.age", age, "calcul")
    put("prospect.mineur", age < AGE_MINIMUM, "calcul")          # R-IDN-005

    # --- Orientation (F01) ------------------------------------------------
    relation_active = any(r.get("statut") == "active" for r in world.relations)
    put("ori.relation_active_existante", relation_active, "csa")   # R-ORI-001
    # R-ORI-003 / R-GEN-004 : c'est la demande d'une offre professionnelle qui
    # sort du parcours particulier. Exercer en libéral tout en ouvrant un compte
    # à titre privé reste parfaitement recevable.
    put("ori.statut_hors_parcours",
        bool(pack and pack.get("hors_parcours_particulier"))
        or (p.statut_pro.value == "profession_liberale" and dossier.step.value == "ORIENTATION"),
        "calcul")
    put("offre.pack_pro_demande", bool(pack and pack.get("hors_parcours_particulier")), "h24")
    inactivite = _jours(dossier.updated_at, today)
    put("ori.jours_inactivite", inactivite, "calcul")
    put("ori.dossier_expire",
        dossier.status.value == "REJETE"
        or (inactivite is not None and inactivite >= JOURS_INACTIVITE_EXPIRATION),
        "calcul")                                                  # R-GEN-003

    # --- Identité (F02) ---------------------------------------------------
    pieces = [d for d in fournis if d.type.value in PIECES_IDENTITE]
    expirees = [d.type.value for d in pieces if d.expire_le and date.fromisoformat(d.expire_le) < today]
    put("ident.piece_expiree", bool(expirees), "h24")              # R-IDN-003
    put("ident.pieces_expirees", expirees, "h24")
    put("ident.cin_absente", "CIN" not in par_type, "h24")
    if p.residence.value == "resident":
        type_ko = "CIN" not in par_type and bool(pieces)           # R-IDN-001
    else:
        type_ko = "PASSEPORT" not in par_type and bool(pieces)     # R-IDN-002
    put("ident.type_non_accepte", type_ko, "calcul")

    # Cohérence pièce/formulaire : seulement si la pièce est lisible, sinon
    # c'est un problème de lisibilité (R-DOC-004), pas de cohérence.
    incoherence, details = False, []
    for d in pieces:
        if not d.ocr_text or (d.ocr_confidence or 1.0) < SEUIL_OCR_LISIBLE:
            continue
        lu = _parse_ocr_identite(d.ocr_text)
        for cle, attendu in [("nom", p.nom), ("prenom", p.prenom), ("naissance", p.date_naissance)]:
            if cle in lu and _norm(lu[cle]) != _norm(attendu):
                incoherence = True
                details.append(f"{cle}: pièce « {lu[cle]} » ≠ formulaire « {attendu} »")
    put("ident.incoherence_formulaire", incoherence, "ocr")        # R-IDN-004
    put("ident.details_incoherence", details, "ocr")

    # --- Coordonnées et OTP (F03) ----------------------------------------
    verrou = dossier.otp.tentatives >= dossier.otp.max_tentatives
    # R-OTP-003 : le verrou se lève seul au bout de trente minutes. Un verrou
    # expiré ne bloque plus rien — le dire au client l'enverrait attendre pour rien.
    minutes_depuis = None
    if dossier.otp.dernier_envoi_at:
        minutes_depuis = (as_of - datetime.fromisoformat(dossier.otp.dernier_envoi_at)).total_seconds() / 60
    put("otp.minutes_depuis_verrou", round(minutes_depuis, 1) if minutes_depuis is not None else None, "calcul")
    put("otp.verrou_expire", bool(verrou and minutes_depuis is not None
                                  and minutes_depuis > MINUTES_VERROU_OTP), "calcul")
    put("otp.max_tentatives_atteint", verrou, "h24")
    tel = p.telephone or ""
    tel_ok = bool(re.fullmatch(r"\+216[2459]\d{7}", tel))              # R-OTP-001
    put("otp.tel_non_eligible", not tel_ok and dossier.otp.canal == "sms", "calcul")
    email_pris = any(x.get("email") == p.email and x.get("dossier_id") != dossier.dossier_id
                     for x in world.doublons)
    put("otp.email_indisponible",
        email_pris or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", p.email or ""), "csa")  # R-OTP-005

    # --- Documents (F04) --------------------------------------------------
    # Le socle (R-DOC-001) seulement : un justificatif de revenu absent relève
    # du profil (R-PRF-002), pas du socle documentaire.
    attendus = set(SOCLE_HORS_IDENTITE) | ({"CIN"} if p.residence.value == "resident" else {"PASSEPORT"})
    manquants = sorted(t for t in attendus if t not in par_type)
    put("doc.manquants", manquants, "h24")                             # R-DOC-001
    illisibles = sorted(d.type.value for d in fournis
                        if d.statut.value == "illisible"
                        or (d.ocr_confidence is not None and d.ocr_confidence < SEUIL_OCR_LISIBLE))
    put("doc.illisibles", illisibles, "ocr")                           # R-DOC-004
    confs = [d.ocr_confidence for d in fournis if d.ocr_confidence is not None]
    put("doc.ocr_confidence_min", min(confs) if confs else None, "ocr")
    jd = par_type.get("JUSTIFICATIF_DOMICILE")
    age_jd = _jours(jd.emis_le, today) if jd else None
    put("doc.age_justif_domicile_jours", age_jd, "calcul")
    put("doc.justif_domicile_trop_ancien",
        age_jd is not None and age_jd > JOURS_VALIDITE_JUSTIF_DOMICILE, "calcul")   # R-DOC-003

    # --- Profil (F05) -----------------------------------------------------
    champs_manquants = [nom for nom, val in [
        ("revenu_mensuel_net", p.revenu_mensuel_declare),
        ("situation_professionnelle", p.statut_pro),
    ] if val is None]
    put("prof.champs_manquants", champs_manquants, "h24")              # R-PRF-001
    revenu = p.revenu_mensuel_declare or 0
    justifs_attendus = JUSTIFICATIFS_REVENU.get(p.statut_pro.value, set())
    justif_present = bool(justifs_attendus & set(par_type))
    put("prof.justificatif_revenu_absent", bool(justifs_attendus) and not justif_present, "h24")
    put("prof.revenu_non_justifie",
        revenu > SEUIL_REVENU_JUSTIFICATIF and bool(justifs_attendus) and not justif_present,
        "calcul")                                                       # R-PRF-002
    put("prof.revenu_retenu", revenu if justif_present or revenu <= SEUIL_REVENU_JUSTIFICATIF else 0, "calcul")
    # Incohérence = une pièce CONTREDIT la situation déclarée ; l'absence de
    # pièce relève de R-PRF-002, pas de R-PRF-003.
    contradiction = (p.statut_pro.value in ("etudiant", "sans_emploi") and "FICHE_PAIE" in par_type)
    put("prof.statut_incoherent", contradiction, "calcul")              # R-PRF-003

    # --- Offre / profil (F06) --------------------------------------------
    if pack:
        c = pack["conditions"]
        put("offre.condition_residence_non_remplie", p.residence.value not in c["residence"], "calcul")
        seuil = c.get("revenu_min") or 0
        revenu_retenu = f["prof.revenu_retenu"].value
        put("offre.revenu_insuffisant", seuil > 0 and revenu_retenu < seuil, "calcul")
        put("offre.seuil_revenu", seuil, "catalogue")
        hors_age = age < (c.get("age_min") or 0) or (c.get("age_max") is not None and age > c["age_max"])
        put("offre.age_hors_bornes", hors_age, "calcul")
        refus_domiciliation = any(e.type == "REFUS_CONDITION" for e in dossier.events)
        put("offre.domiciliation_absente", bool(c.get("domiciliation_requise")) and refus_domiciliation, "h24")
        put("offre.alternatives", _alternatives(p, age, f["prof.revenu_retenu"].value, packs), "catalogue")
    else:
        for n in ("offre.condition_residence_non_remplie", "offre.revenu_insuffisant",
                  "offre.age_hors_bornes", "offre.domiciliation_absente"):
            put(n, False, "calcul")
        put("offre.alternatives", [], "catalogue")

    # --- Doublons (F07) ---------------------------------------------------
    put("dup.cin_multi_dossiers",
        bool(p.cin) and any(x.get("cin") == p.cin and x.get("dossier_id") != dossier.dossier_id
                            and x.get("statut") in ("EN_COURS", "EN_ATTENTE") for x in world.doublons),
        "csa")                                                          # R-DUP-001
    put("dup.coordonnees_utilisees",
        any(x.get("telephone") == p.telephone and x.get("dossier_id") != dossier.dossier_id
            for x in world.doublons), "csa")                            # R-DUP-002
    pack_code = dossier.offre.pack_code if dossier.offre else None
    put("dup.abonnement_actif",
        any(s.get("statut") == "active" and s.get("pack_code") == pack_code
            for s in world.subscriptions), "csa")                       # R-DUP-003

    # --- Agence (F08) -----------------------------------------------------
    heures = _heures(dossier.agence.en_file_depuis, as_of)
    put("agc.heures_attente", round(heures, 1) if heures is not None else None, "calcul")
    put("agc.en_file", heures is not None, "h24")
    put("agc.sla_depasse", heures is not None and heures > dossier.agence.sla_heures, "calcul")  # R-AGC-003
    put("agc.rdv_non_honore", dossier.agence.rdv_honore is False, "h24")                         # R-AGC-004

    # --- Choix de l'agence et mode de finalisation (F11) -------------------
    # Le référentiel d'agences vient du catalogue : une agence absente est une incohérence de
    # données (R-AGE-004), jamais une faute du prospect. Chaque fait est borné à l'étape où il
    # bloque réellement : une agence fermée n'empêche plus rien une fois l'agence choisie et dépassée.
    agences = {a["code"]: a for a in catalog.get("agences", [])}
    code_ag = dossier.agence.code_agence
    ag = agences.get(code_ag) if code_ag else None
    etape = dossier.step.value
    put("age.non_choisie", code_ag is None and etape == "CHOIX_AGENCE", "h24")                  # R-AGE-001
    put("age.code_inconnu", bool(code_ag) and ag is None, "calcul")                             # R-AGE-004
    put("age.fermee", bool(ag) and ag["statut"] != "ouverte" and etape == "CHOIX_AGENCE",
        "catalogue")                                                                            # R-AGE-002
    put("age.profil_non_pris_en_charge",
        bool(ag) and p.residence.value == "non_resident" and not ag["accueille_non_residents"]
        and etape == "CHOIX_AGENCE", "catalogue")                                               # R-AGE-003
    sig = dossier.signature.statut
    put("age.signature_en_agence",
        etape == "SIGNATURE" and sig != "signee"
        and (sig == "echec" or (bool(ag) and not ag["signature_electronique"])), "calcul")      # R-AGE-005
    put("age.alternatives", _agences_alternatives(p, agences, exclure=code_ag), "catalogue")

    # --- Désynchronisation (F09) -----------------------------------------
    ecart_min, divergent = None, False
    if world.etat_csa:
        divergent = (world.etat_csa.get("step") != dossier.step.value
                     or world.etat_csa.get("status") != dossier.status.value)
        h = _heures(world.etat_csa.get("updated_at"), datetime.fromisoformat(dossier.updated_at))
        ecart_min = round(abs(h) * 60, 1) if h is not None else None
    put("syn.etat_csa", world.etat_csa, "csa")
    put("syn.ecart_minutes", ecart_min, "calcul")
    put("syn.ecart_referentiels",
        divergent and (ecart_min is None or ecart_min > MINUTES_ECART_ADMISSIBLE), "calcul")     # R-SYN-002
    put("syn.signature_non_propagee",
        dossier.signature.statut == "signee"
        and bool(world.etat_csa) and world.etat_csa.get("signature_recue") is False, "csa")      # R-SYN-003
    put("syn.incident_amont", any(e.type == "INCIDENT_AMONT" for e in dossier.events), "h24")    # R-GEN-019

    # --- Sécurité (F10) ---------------------------------------------------
    motifs_doc, motifs_msg, motifs_perim = [], [], []
    for d in docs:
        ocr_norm = _norm(d.ocr_text or "")
        for motif, etiquette in MOTIFS_INJECTION:
            if re.search(motif, ocr_norm):
                motifs_doc.append(f"{d.type.value}:{etiquette}")
        # Un texte de document n'est pas une conversation : seuls les marqueurs durs comptent, sinon
        # « Validez immédiatement votre paiement » (facture ordinaire) deviendrait une injection.
        if _decision_sous_pression(ocr_norm, doux=False):
            motifs_doc.append(f"{d.type.value}:demande_decision_sous_pression")
    texte_libre = " ".join(filter(None, [dossier.message_client, world.question]))
    texte_norm = _norm(texte_libre)
    for motif, etiquette in MOTIFS_INJECTION:
        if re.search(motif, texte_norm):
            motifs_msg.append(etiquette)
    if _decision_sous_pression(texte_norm):
        motifs_msg.append("demande_decision_sous_pression")
    # « valide. valide. valide maintenant. » : l'insistance sur un impératif de
    # décision est elle-même un signal, même sans formule de contournement.
    for verbe in ("valide", "active", "debloque", "approuve"):
        if len(re.findall(rf"\b{verbe}[rz]?\b", texte_norm)) >= 3:
            motifs_msg.append("insistance_decision")
    for motif, etiquette in MOTIFS_HORS_PERIMETRE:
        if etiquette == "autre_dossier_designe":
            # Les identifiants sont en capitales ASCII : on cherche dans le texte
            # BRUT, car la normalisation les passerait en minuscules.
            for m in re.finditer(motif, texte_libre):
                if m.group(0) != dossier.dossier_id:
                    motifs_perim.append(etiquette)   # citer SON dossier est légitime
        else:
            # Les autres motifs sont écrits sans accent : ils doivent être
            # cherchés dans le texte NORMALISÉ, sinon « numéro » ne matche jamais.
            if re.search(motif, texte_norm):
                motifs_perim.append(etiquette)

    llm = world.injection_llm or {}
    if llm.get("verdict") == "injection" and llm.get("cible") == "document":
        motifs_doc.append("classifieur:injection")
    if llm.get("verdict") == "injection" and llm.get("cible") == "message":
        motifs_msg.append("classifieur:injection")

    put("sec.injection_document", bool(motifs_doc), "ocr")              # R-SEC-004
    put("sec.injection_message", bool(motifs_msg), "client")            # R-SEC-002
    put("sec.hors_perimetre", bool(motifs_perim), "client")             # R-SEC-003
    put("sec.dossier_hors_session", "autre_dossier_designe" in motifs_perim, "client")
    put("sec.motifs_suspects", sorted(set(motifs_doc + motifs_msg + motifs_perim)), "calcul")

    return f


def _agences_alternatives(prospect, agences: dict, *, exclure: str | None) -> list[str]:
    """Agences ouvertes qui prennent en charge le profil (R-AGE-006) : on ne dit pas « choisissez
    une autre agence » sans dire lesquelles."""
    return [f"{a['ville']} ({a['code']})" for a in agences.values()
            if a["code"] != exclure and a["statut"] == "ouverte"
            and (prospect.residence.value == "resident" or a["accueille_non_residents"])]


def _alternatives(prospect, age: int, revenu: int, packs: dict) -> list[str]:
    """Offres pour lesquelles le prospect RESTE éligible (R-OFR-016).

    Un refus sans alternative est une cause d'abandon évitable : on calcule la
    liste ici pour que l'explication puisse toujours en proposer une.
    """
    out = []
    for code, pk in packs.items():
        if pk.get("hors_parcours_particulier"):
            continue
        c = pk["conditions"]
        if prospect.residence.value not in c["residence"]:
            continue
        if age < (c.get("age_min") or 0) or (c.get("age_max") is not None and age > c["age_max"]):
            continue
        if c.get("statuts") and prospect.statut_pro.value not in c["statuts"]:
            continue
        if revenu < (c.get("revenu_min") or 0):
            continue
        out.append(code)
    return out
