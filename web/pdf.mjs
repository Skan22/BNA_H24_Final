// Imprime une page HTML locale en PDF A4 avec pied de page numéroté. Appelé par tools/build_pdf.py.
import { chromium } from "@playwright/test";

const [, , entree, sortie, titre = ""] = process.argv;
const navigateur = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ["--no-sandbox"] });
const page = await navigateur.newPage();
await page.goto("file://" + entree);
await page.pdf({
  path: sortie,
  format: "A4",
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate:
    `<div style="width:100%;font:8px sans-serif;color:#6b7580;padding:0 16mm;display:flex;justify-content:space-between">` +
    `<span>${titre.replace(/[<>&]/g, "")}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
  margin: { top: "18mm", bottom: "20mm", left: "16mm", right: "16mm" },
});
await navigateur.close();
