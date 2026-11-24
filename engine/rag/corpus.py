"""BOUSSOLA — corpus ancré et recherche lexicale.

Choix structurant : les citations d'un diagnostic ne viennent PAS d'une
recherche de similarité. Elles viennent des ancres déclarées par le nœud causal
retenu, et sont simplement résolues ici. Une recherche approchée peut ramener
une règle voisine mais fausse ; une ancre, non.

La recherche lexicale (BM25) ne sert qu'aux questions libres, et ne peut jamais
introduire une règle que la cause n'a pas déjà citée.
"""
from __future__ import annotations

import math
import pathlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import yaml

from contracts.models import Citation

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "kit" / "corpus"

MOTS_VIDES = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "et", "ou", "a", "au", "aux", "en",
    "par", "pour", "sur", "dans", "est", "sont", "ne", "pas", "qui", "que", "ce", "cette", "ces",
    "son", "sa", "ses", "il", "elle", "on", "l", "y", "se", "plus", "moins", "tout", "toute",
}


def _tokens(txt: str) -> list[str]:
    txt = unicodedata.normalize("NFKD", txt.lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", txt) if t not in MOTS_VIDES and len(t) > 1]


@dataclass
class Rule:
    anchor: str
    titre_regle: str
    texte: str
    doc_id: str
    doc_titre: str
    version: str
    domaine: str
    effective_date: str

    def to_citation(self, *, max_chars: int = 420) -> Citation:
        extrait = " ".join(self.texte.split())
        if len(extrait) > max_chars:
            extrait = extrait[: max_chars - 1].rsplit(" ", 1)[0] + "…"
        return Citation(anchor=self.anchor, doc_id=self.doc_id,
                        titre=f"{self.doc_titre} — {self.titre_regle}",
                        extrait=extrait, version=self.version)


def _parse(path: pathlib.Path) -> list[Rule]:
    raw = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        return []
    meta, body = yaml.safe_load(m.group(1)), m.group(2)
    rules = []
    # Chaque « ## R-XXX-NNN — Titre » ouvre une règle et ferme la précédente.
    parts = re.split(r"^## (R-[A-Z]+-\d+)\s*[—-]\s*(.+)$", body, flags=re.M)
    for i in range(1, len(parts), 3):
        anchor, titre, texte = parts[i], parts[i + 1].strip(), parts[i + 2].strip()
        rules.append(Rule(anchor=anchor, titre_regle=titre, texte=texte,
                          doc_id=meta["doc_id"], doc_titre=meta["titre"],
                          version=str(meta["version"]), domaine=meta.get("domaine", ""),
                          effective_date=str(meta.get("effective_date", ""))))
    return rules


class Corpus:
    def __init__(self, directory: pathlib.Path = CORPUS_DIR):
        self.rules: dict[str, Rule] = {}
        for path in sorted(directory.glob("*.md")):
            for rule in _parse(path):
                if rule.anchor in self.rules:
                    raise ValueError(f"ancre dupliquée dans le corpus : {rule.anchor}")
                self.rules[rule.anchor] = rule
        self._index()

    def _index(self) -> None:
        self.docs_tokens = {a: _tokens(f"{r.titre_regle} {r.texte}") for a, r in self.rules.items()}
        self.df = Counter()
        for toks in self.docs_tokens.values():
            self.df.update(set(toks))
        self.n = len(self.docs_tokens) or 1
        self.avgdl = sum(len(t) for t in self.docs_tokens.values()) / self.n

    def resolve(self, anchors: list[str]) -> list[Citation]:
        """Ancres -> citations, dans l'ordre, sans doublon. Une ancre inconnue est ignorée."""
        vus, out = set(), []
        for a in anchors:
            if a in vus or a not in self.rules:
                continue
            vus.add(a)
            out.append(self.rules[a].to_citation())
        return out

    def search(self, query: str, k: int = 5, *, within: set[str] | None = None) -> list[Rule]:
        """BM25 simple, sans dépendance et hors réseau.

        `within` restreint la recherche à un sous-ensemble d'ancres : c'est ainsi
        que l'on garantit qu'une question libre ne fait pas surgir une règle
        étrangère à la cause retenue.
        """
        q = _tokens(query)
        if not q:
            return []
        k1, b, scores = 1.5, 0.75, {}
        for anchor, toks in self.docs_tokens.items():
            if within is not None and anchor not in within:
                continue
            tf, dl, s = Counter(toks), len(toks), 0.0
            for term in q:
                if term not in tf:
                    continue
                idf = math.log(1 + (self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                s += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * dl / self.avgdl))
            if s > 0:
                scores[anchor] = s
        best = sorted(scores, key=lambda a: -scores[a])[:k]
        return [self.rules[a] for a in best]

    def anchors_for_passage_check(self, anchors: list[str]) -> str:
        """Texte concaténé des règles citées, pour la vérification d'ancrage."""
        return "\n\n".join(f"[{a}] {self.rules[a].texte}" for a in anchors if a in self.rules)


CORPUS = Corpus()
