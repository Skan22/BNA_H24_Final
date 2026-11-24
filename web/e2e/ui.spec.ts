import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const CLIENT_PW = process.env.CLIENT_PASSWORD || "client-demo-change-me";
const AGENT_PW = process.env.AGENT_PASSWORD || "agent-demo-change-me";
// Les dossiers sont retrouvés par cause via le mode démonstration : les numéros changent quand le kit est régénéré.
async function dossierPour(request: import("@playwright/test").APIRequestContext, cause: string): Promise<string> {
  const demo = await (await request.get("/api/v1/auth/demo")).json();
  return demo.scenarios.find((x: { cause_id: string }) => x.cause_id === cause).dossier_id;
}
let DOSSIER_PIECE_EXPIREE = "";   // cause C-IDN-001, résolue avant les tests
test.beforeAll(async ({ request }) => { DOSSIER_PIECE_EXPIREE = await dossierPour(request, "C-IDN-001"); });

async function connecter(page: Page, role: "agent" | "client") {
  await page.goto("/login");
  await page.getByLabel("Espace").selectOption(role);
  if (role === "client") await page.getByLabel("Numéro de dossier").fill(DOSSIER_PIECE_EXPIREE);
  await page.getByLabel("Mot de passe").fill(role === "agent" ? AGENT_PW : CLIENT_PW);
  await page.getByRole("button", { name: "Accéder à mon espace" }).click();
  await expect(page).toHaveURL(role === "agent" ? /\/agent/ : /\/client/);
}

async function accessible(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`)).toEqual([]);
}

test("anonyme : redirigé vers la connexion, mauvais mot de passe refusé", async ({ page }) => {
  await page.goto("/client");
  await expect(page).toHaveURL(/\/login/);
  await accessible(page);
  await page.getByLabel("Mot de passe").fill("mauvais");
  await page.getByRole("button", { name: "Accéder à mon espace" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Identifiants invalides" })).toBeVisible();
});

test("client : explication, preuve, simulation, arabe hors ligne, pas d'accès agent", async ({ page }) => {
  await connecter(page, "client");
  await page.getByRole("button", { name: "Savoir pourquoi" }).click();
  await expect(page.getByRole("heading", { name: "Ce qu'il vous reste à faire" })).toBeVisible();
  const corps = await page.locator("main").innerText();
  expect(corps).not.toMatch(/\bC-[A-Z]{3}-\d{3}\b/);                 // aucun code de cause
  await accessible(page);

  await page.getByRole("button", { name: "Pourquoi cette réponse ?" }).click();
  await page.getByRole("button", { name: "Et si c'était réglé ?" }).first().click();
  await expect(page.getByText("Simulation uniquement")).toBeVisible();
  await accessible(page);

  await page.getByLabel("Langue").selectOption("ar");
  await page.getByRole("button", { name: "Savoir pourquoi" }).click();
  await expect(page.locator('.bubble[lang="ar"]')).toContainText("طلبك متوقف");
  await expect(page.getByRole("note")).toBeVisible();

  await page.goto("/agent");
  await expect(page).toHaveURL(/\/client/);                           // un client n'ouvre pas le poste agent
});

test("agent : diagnostic, preuve, simulation, escalade en deux temps, évaluation", async ({ page }) => {
  await connecter(page, "agent");
  await page.getByLabel("Dossier à analyser").selectOption(DOSSIER_PIECE_EXPIREE);
  await page.getByRole("button", { name: "Analyser" }).click();
  await expect(page.getByRole("heading", { name: "Causes probables" })).toBeVisible();
  await page.getByRole("button", { name: "Et si ce blocage était levé ?" }).first().click();
  await expect(page.getByText(/Hypothèse/)).toBeVisible();
  await accessible(page);

  await page.getByRole("button", { name: "Preuve", exact: true }).click();
  await expect(page.getByText("Faits observés").first()).toBeVisible();
  await page.getByRole("button", { name: "Trace", exact: true }).click();
  await expect(page.getByText("chaîne intègre")).toBeVisible();

  await page.goto("/jury");
  await expect(page.getByText("Évaluation mesurée")).toBeVisible();
});

test("agent : escalade — brouillon puis confirmation, sur un dossier en repli sûr", async ({ page, request }) => {
  await connecter(page, "agent");
  await page.getByLabel("Dossier à analyser").selectOption(await dossierPour(request, "C-UNK-000"));
  await page.getByRole("button", { name: "Analyser" }).click();
  await expect(page.getByText("Escalade").first()).toBeVisible();
  await page.getByRole("button", { name: "Préparer le brouillon" }).click();
  await page.getByRole("button", { name: "J'acquitte et je confirme" }).click();
  await expect(page.getByText(/Confirmée \(simulation\)/)).toBeVisible();
});
