import Layout from "@/components/Layout";
import { getCurrentUser } from "@/lib/api";

export default function HomePage() {
  const user = typeof window !== "undefined" ? getCurrentUser() : null;

  return (
    <Layout>
      <div className="card">
        <h2>Bienvenido{user ? `, ${user.nombre}` : ""}</h2>
        <p>
          Este es el panel web mínimo de Jacobea AI (Fase 1). Aquí puedes ver los usuarios,
          gastos y tareas registrados, incluyendo los que los técnicos registran directamente
          por WhatsApp.
        </p>
        <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>
          Tu rol: <span className="badge">{user?.rol}</span>
        </p>
      </div>
    </Layout>
  );
}
