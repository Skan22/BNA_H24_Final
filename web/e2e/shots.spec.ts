import { test, type Page } from "@playwright/test";

// Captures d'écran du README : `make shots` (pile en marche requise) -> docs/img/*.png
const CLIENT_PW = process.env.CLIENT_PASSWORD || "client-demo-change-me";
const AGENT_PW = process.env.AGENT_PASSWORD || "agent-demo-change-me";
const OUT = "../docs/img";

async function scenario(page: Page, cause: string): Promise<string> {
  const demo = await (await page.request.get("/api/v1/auth/demo")).json();
  return demo.scenarios.find((x: { cause_id: string }) => x.cause_id === cause).dossier_id;
}

async function login(page: Page, role: "client" | "agent", dossier?: string) {
  await page.goto("/login");
  await page.getByLabel("Espace").selectOption(role);
  if (dossier) await page.getByLabel("Numéro de dossier").fill(dossier);
  await page.getByLabel("Mot de passe").fill(role === "client" ? CLIENT_PW : AGENT_PW);
  await page.getByRole("button", { name: "Accéder à mon espace" }).click();
}

test("captures", async ({ page }) => {
  await page.addInitScript(() => {
    document.addEventListener("DOMContentLoaded", () => {
      const s = document.createElement("style");
      s.textContent = "nextjs-portal{display:none!important}";
      document.head.appendChild(s);
    });
  });
  const agence = await scenario(page, "C-AGE-002");
  const piege = await scenario(page, "C-SEC-001");

  await login(page, "client", agence);
  await page.getByRole("button", { name: "Savoir pourquoi" }).click();
  await page.locator(".stepper .now").waitFor();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/client.png`, fullPage: true });

  await page.getByRole("button", { name: /Se déconnecter/ }).click();
  await login(page, "agent");
  await page.getByLabel("Scénario de démonstration").selectOption(piege);
  await page.getByRole("button", { name: "Analyser" }).click();
  await page.getByRole("heading", { name: "Causes probables" }).waitFor();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/agent.png`, fullPage: true });
  await page.getByRole("button", { name: "Preuve", exact: true }).click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/preuve.png`, fullPage: true });

  await page.goto("/jury");
  await page.getByText("Évaluation mesurée").waitFor();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/jury.png`, fullPage: true });
});
