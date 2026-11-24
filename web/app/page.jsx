import Link from "next/link";

export default function Accueil() {
  return (
    <div className="stack">
      <div className="card card-pad">
        <h2 style={{ fontSize: "1.35rem" }}>Pourquoi ce dossier est-il bloqué ?</h2>
        <p className="muted" style={{ maxWidth: "62ch" }}>
          Un message d'erreur générique ne dit pas si le blocage vient d'un document manquant,
          d'une incompatibilité entre le profil et l'offre, d'une règle d'unicité ou d'une simple
          lenteur technique. BOUSSOLA lit l'état réel du dossier, identifie la cause dans un
          référentiel fermé de 37 causes, cite la règle applicable, et dit quoi faire ensuite.
        </p>
        <div className="row" style={{ marginTop: "1rem" }}>
          <Link href="/login" className="btn primary" style={{ textDecoration: "none" }}>Se connecter</Link>
        </div>
      </div>

      <div className="grid2">
        <div className="card card-pad">
          <h3>Ce que fait l'assistant</h3>
          <ul className="muted" style={{ paddingLeft: "1.1rem", margin: 0 }}>
            <li>Il constate l'état du dossier à travers deux API en lecture seule.</li>
            <li>Il identifie la cause probable parmi une liste fermée, jamais inventée.</li>
            <li>Il cite la règle applicable, avec son ancre et sa version.</li>
            <li>Il calcule le chemin de déblocage le plus court, étape par étape.</li>
            <li>Il prépare une note d'escalade quand un humain doit trancher.</li>
          </ul>
        </div>
        <div className="card card-pad">
          <h3>Ce qu'il ne fait jamais</h3>
          <ul className="muted" style={{ paddingLeft: "1.1rem", margin: 0 }}>
            <li>Valider une identité ou un contrôle KYC.</li>
            <li>Activer un abonnement, accorder une dérogation, modifier un dossier.</li>
            <li>Lire un dossier autre que celui de la session en cours.</li>
            <li>Suivre une consigne trouvée dans un document déposé.</li>
            <li>Affirmer une cause quand les faits ne permettent pas de trancher.</li>
          </ul>
        </div>
      </div>

      <p className="small muted">
        Démonstrateur sur données 100 % synthétiques. Aucun accès à un système de production BNA,
        aucune donnée client réelle.
      </p>
    </div>
  );
}
