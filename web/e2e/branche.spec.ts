import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const CLIENT_PW = process.env.CLIENT_PASSWORD || "client-demo-change-me";
const AGENT_PW = process.env.AGENT_PASSWORD || "agent-demo-change-me";

async function dossierDeCause(request: APIRequestContext, cause: string): Promise<string> {
  const demo = await (await request.get("/api/v1/auth/demo")).json();
  return demo.scenarios.find((x: { cause_id: string }) => x.cause_id === cause).dossier_id;
}

async function accessible(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`)).toEqual([]);
}

test("étape « choix de l'agence » : le client la voit dans son parcours, avec des agences de remplacement", async ({ page, request }) => {
  const dossier = await dossierDeCause(request, "C-AGE-002"); // agence choisie temporairement fermée
  await page.goto("/login");
  await page.getByLabel("Espace").selectOption("client");
  await page.getByLabel("Numéro de dossier").fill(dossier);
  await page.getByLabel("Mot de passe").fill(CLIENT_PW);
  await page.getByRole("button", { name: "Accéder à mon espace" }).click();
  await page.getByRole("button", { name: "Savoir pourquoi" }).click();
  await expect(page.locator(".stepper .now")).toHaveText("Agence"); // la 2e étape du parcours est active
  await expect(page.locator(".bubble")).toContainText("choix de votre agence");
  await expect(page.locator("ol.actions").getByText(/Agences ouvertes qui prennent en charge votre profil/)).toBeVisible();
  expect(await page.locator("main").innerText()).not.toMatch(/AG-6077|\bC-[A-Z]{3}-\d{3}\b/); // ni code interne, ni agence fermée
  await accessible(page);
  await page.getByLabel("Langue").selectOption("ar");
  await page.getByRole("button", { name: "Savoir pourquoi" }).click();
  await expect(page.locator('.bubble[lang="ar"]')).toContainText("اختيار الوكالة");
});

test("agent : scénario de démonstration « rattachement d'agence » -> back-office, escalade", async ({ page, request }) => {
  const dossier = await dossierDeCause(request, "C-AGE-004");
  await page.goto("/login");
  await page.getByLabel("Mot de passe").fill(AGENT_PW);
  await page.getByRole("button", { name: "Accéder à mon espace" }).click();
  await page.getByLabel("Scénario de démonstration").selectOption(dossier);
  await page.getByRole("button", { name: "Analyser" }).click();
  await expect(page.getByRole("heading", { name: "Causes probables" })).toBeVisible();
  await expect(page.locator("b").filter({ hasText: "Rattachement à l'agence à corriger par nos équipes" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Escalade" })).toBeVisible();
});
