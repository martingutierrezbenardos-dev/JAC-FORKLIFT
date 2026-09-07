import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { CurrentUser, getCurrentUser, getToken, logout } from "@/lib/api";

export default function Layout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getCurrentUser());
    setChecked(true);
  }, [router]);

  if (!checked) {
    return null;
  }

  return (
    <div className="layout">
      <div className="topbar">
        <div className="topbar-brand">Jacobea AI — Panel interno</div>
        <nav className="topbar-nav">
          <Link href="/">Inicio</Link>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/expenses">Gastos</Link>
          <Link href="/tasks">Tareas</Link>
          <Link href="/services">Servicios</Link>
          <Link href="/customers">Clientes</Link>
          <Link href="/machines">Máquinas</Link>
          <Link href="/vehicles">Vehículos</Link>
          <Link href="/cranes">Grúas</Link>
          <Link href="/users">Usuarios</Link>
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              logout();
              router.push("/login");
            }}
          >
            Salir ({user?.nombre})
          </a>
        </nav>
      </div>
      <div className="content">{children}</div>
    </div>
  );
}
