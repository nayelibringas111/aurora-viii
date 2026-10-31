import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/app/auth";
import { IconBook, IconFolder, IconHome, IconMenu, IconNet, IconShield } from "./Icons";

type Crumb = { label: string; to?: string };
const CrumbCtx = createContext<(c: Crumb[]) => void>(() => {});

/** Cada página declara su ruta de migas: <Crumbs items=[...] /> */
export function useCrumbs(items: Crumb[]) {
  const set = useContext(CrumbCtx);
  const key = JSON.stringify(items);
  useEffect(() => { set(items); }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
}

export function Logo({ size = 28 }: { size?: number }) {
  return <img src="/favicon.svg" width={size} height={size} alt="" />;
}

export function Shell() {
  const { me, signOut } = useAuth();
  const [crumbs, setCrumbs] = useState<Crumb[]>([]);
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);

  const nav: { to: string; label: string; icon: ReactNode; end?: boolean }[] = [
    { to: "/", label: "Inicio", icon: <IconHome />, end: true },
    { to: "/proyectos", label: "Proyectos", icon: <IconFolder /> },
    { to: "/fundamentos", label: "Fundamentos", icon: <IconBook /> },
    { to: "/familias", label: "Catálogo de redes", icon: <IconNet /> },
  ];
  return (
    <CrumbCtx.Provider value={setCrumbs}>
      <div className="shell">
        <aside className={`sidebar${open ? " open" : ""}`} aria-label="Navegación principal">
          <Link to="/" className="brand"><Logo /><span className="brand-word">Aurora<span>VIII</span></span></Link>
          <nav className="nav">
            {nav.map((n) => <NavLink key={n.to} to={n.to} end={n.end}>{n.icon}{n.label}</NavLink>)}
            {me?.is_admin && <><div className="nav-sep" /><NavLink to="/admin"><IconShield />Administración</NavLink></>}
          </nav>
          <div className="sidebar-foot">
            <strong>{me?.display_name}</strong>
            <div>{me?.email}</div>
            <div style={{ marginTop: 6 }}>{me?.is_admin ? "Administrador" : "Usuario"}</div>
            <button className="btn btn-sm" style={{ marginTop: 10, width: "100%" }} onClick={() => signOut()}>Cerrar sesión</button>
          </div>
        </aside>
        <div className="main">
          <header className="topbar">
            <div className="row">
              <button className="btn btn-sm btn-ghost menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Abrir menú"><IconMenu /></button>
              <nav className="crumbs" aria-label="Migas de pan">
                {crumbs.map((c, i) => (
                  <span key={i} className="row" style={{ gap: 8 }}>
                    {i > 0 && <span className="sep">/</span>}
                    {c.to ? <Link to={c.to}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
                  </span>
                ))}
              </nav>
            </div>
          </header>
          <main className="content"><Outlet /></main>
        </div>
      </div>
    </CrumbCtx.Provider>
  );
}
