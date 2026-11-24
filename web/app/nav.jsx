"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "./session";

const LIENS = {
  client: [["/client", "Ma demande"]],
  agent: [["/agent", "Poste agent"], ["/jury", "Évaluation"]],
};

export default function Nav() {
  const path = usePathname();
  const { session, logout } = useSession();
  if (!session) return null;
  return (
    <nav className="nav" aria-label="Navigation principale">
      {(LIENS[session.role] || []).map(([href, label]) => (
        <Link key={href} href={href} className={path === href ? "on" : ""}>{label}</Link>
      ))}
      <button onClick={logout} style={{ marginLeft: "auto" }}>Se déconnecter ({session.role === "agent" ? "agent" : "client"})</button>
    </nav>
  );
}
