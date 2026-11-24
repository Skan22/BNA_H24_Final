import "./globals.css";
import Nav from "./nav";
import { SessionProvider } from "./session";

export const metadata = {
  title: "BOUSSOLA — diagnostic H24",
  description: "Assistant de diagnostic des blocages du parcours « Devenir client » BNA H24",
};

export default function RootLayout({ children }) {
  return (
    <html lang="fr">
      <body>
        <a className="skip-link" href="#contenu">Aller au contenu</a>
        <SessionProvider>
        <header className="topbar">
          <div className="topbar-in">
            <div className="brand">
              <span className="brand-mark">◉</span>
              <span>BOUSSOLA
                <small>Diagnostic du parcours H24 — données synthétiques</small>
              </span>
            </div>
            <Nav />
          </div>
        </header>
        <main id="contenu">{children}</main>
        </SessionProvider>
      </body>
    </html>
  );
}
