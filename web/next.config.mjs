/** @type {import('next').NextConfig} */
const moteur = process.env.BOUSSOLA_API || "http://127.0.0.1:8000";

export default {
  // Le moteur tourne à côté ; on relaie /api vers FastAPI pour garder une seule
  // origine côté navigateur — pas de CORS à gérer, et l'interface ne connaît
  // qu'un seul chemin. BOUSSOLA_API permet de pointer ailleurs si 8000 est pris.
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Content-Security-Policy", value:
        // 'unsafe-inline' : hydratation Next sans nonce ; 'unsafe-eval' seulement en développement.
        `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; ` +
        `base-uri 'self'; form-action 'self'; script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"}` },
      { key: "Referrer-Policy", value: "no-referrer" },
    ] }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${moteur}/:path*` }];
  },
};
