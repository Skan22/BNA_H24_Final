import { expect, test, type Page } from "@playwright/test";

// Démonstration filmée (environ 2 minutes). Les sous-titres sont posés dans la page : ils apparaissent dans la vidéo.
const CLIENT_PW = process.env.CLIENT_PASSWORD || "client-demo-change-me";
const AGENT_PW = process.env.AGENT_PASSWORD || "agent-demo-change-me";

async function legende(page: Page, texte: string, ms = 3200) {
  await page.evaluate((t) => {
    let el = document.getElementById("film-legende");
    if (!el) {
      el = document.createElement("div");
      el.id = "film-legende";
      el.style.cssText =
        "position:fixed;left:0;right:0;bottom:0;z-index:99999;padding:14px 24px;background:rgba(15,107,71,.96);" +
        "color:#fff;font:600 20px/1.35 system-ui,sans-serif;text-align:center";
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, texte);
  await page.waitForTimeout(ms);
}

async function scenario(page: Page, cause: string): Promise<string> {
  const demo = await (await page.request.get("/api/v1/auth/demo")).json();
  return demo.scenarios.find((x: { cause_id: string }) => x.cause_id === cause).dossier_id;
}

test("démonstration BOUSSOLA — parcours H24 avec choix de l'agence", async ({ page }) => {
  const agence = await scenario(page, "C-AGE-002");
  const inconnu = await scenario(page, "C-AGE-004");
  const piege = await scenario(page, "C-SEC-001");

  // 1 — le client
  await page.goto("/");
  await legende(page, "BOUSSOLA : un message d'erreur générique ne dit pas pourquoi. L'assistant explique, cite la règle, et ne décide jamais.", 4500);
  await page.goto("/login");
  await page.getByLabel("Espace").selectOption("client");
  await page.getByLabel("Numéro de dossier").fill(agence);
  await page.getByLabel("Mot de passe").fill(CLIENT_PW);
  await legende(page, "Côté client : une session = un seul dossier, choisi à la connexion.", 2500);
  await page.getByRole("button", { name: "Accéder à mon espace" }).click();
  await page.getByRole("button", { name: "Savoir pourquoi" }).click();
  await expect(page.locator(".stepper .now")).toHaveText("Agence");
  await legende(page, "Le parcours compte maintenant le CHOIX DE L'AGENCE comme première étape, comme sur BNA H24.", 4000);
  await legende(page, "Ici, l'agence choisie est fermée : le client sait quoi faire, et quelles agences sont ouvertes pour son profil.", 4500);
  await page.getByRole("button", { name: "Pourquoi cette réponse ?" }).click();
  await page.getByRole("button", { name: "Et si c'était réglé ?" }).first().click();
  await legende(page, "« Et si c'était réglé ? » : une simulation en lecture seule. Rien n'est modifié, rien n'est approuvé.", 4500);
  await page.getByLabel("Langue").selectOption("ar");
  await page.getByRole("button", { name: "Savoir pourquoi" }).click();
  await legende(page, "Arabe et anglais, même hors ligne : texte pré-écrit annoncé comme tel, détail des actions en français.", 4000);
  await page.getByRole("button", { name: /Se déconnecter/ }).click();

  // 2 — l'agent
  await page.getByLabel("Espace").selectOption("agent");
  await page.getByLabel("Mot de passe").fill(AGENT_PW);
  await page.getByRole("button", { name: "Accéder à mon espace" }).click();
  await page.getByLabel("Scénario de démonstration").selectOption(inconnu);
  await page.getByRole("button", { name: "Analyser" }).click();
  await expect(page.getByRole("heading", { name: "Causes probables" })).toBeVisible();
  await legende(page, "Côté agent : cause, confiance, faits observés, règles citées. Ici un rattachement d'agence à corriger : donnée interne, pas une faute du client.", 5000);
  await page.getByRole("button", { name: "Preuve", exact: true }).click();
  await legende(page, "Chaîne de preuve : faits observés, règle citée, suite. Refusée si le dossier a changé entre-temps.", 4500);
  await page.getByRole("button", { name: "Diagnostic", exact: true }).click();
  await page.getByRole("button", { name: "Préparer le brouillon" }).click();
  await legende(page, "Escalade en deux temps : brouillon, puis confirmation par un agent connecté. Le serveur ne reçoit jamais d'acquittement dans la requête.", 5000);
  await page.getByRole("button", { name: "J'acquitte et je confirme" }).click();
  await legende(page, "Confirmée (simulation). Aucune décision bancaire automatisée.", 3000);

  // 3 — la manipulation
  await page.getByLabel("Scénario de démonstration").selectOption(piege);
  await page.getByRole("button", { name: "Analyser" }).click();
  await expect(page.getByRole("heading", { name: "Causes probables" })).toBeVisible();
  await legende(page, "Une facture piégée contient « valider automatiquement ». Le contenu n'est jamais une consigne : signalé, escaladé, jamais exécuté.", 5000);
  await page.getByRole("button", { name: "Trace", exact: true }).click();
  await legende(page, "Journal d'audit chaîné : chaque ligne porte l'empreinte de la précédente.", 3500);

  // 4 — les chiffres, honnêtement
  await page.goto("/jury");
  await expect(page.getByText("Évaluation mesurée")).toBeVisible();
  await legende(page, "Mesures recalculées. Limite assumée : le kit est synthétique, il mesure la couverture, pas la précision sur de vrais dossiers.", 5500);
});
