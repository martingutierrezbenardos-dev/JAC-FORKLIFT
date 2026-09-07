import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type ServiceOrderRow = {
  id: string;
  numero: string;
  fecha: string;
  motivo: string | null;
  diagnostico: string | null;
  trabajo_realizado: string | null;
  estado: string;
};

export default function ServicesPage() {
  const [orders, setOrders] = useState<ServiceOrderRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ServiceOrderRow[]>("/api/service-orders")
      .then(setOrders)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de servicios.")
      );
  }, []);

  return (
    <Layout>
      <div className="card">
        <h2>Servicios técnicos</h2>
        <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>
          Órdenes de servicio registradas por los técnicos, incluyendo las reportadas
          directamente por WhatsApp.
        </p>
        {error && <div className="error-box">{error}</div>}
        {!error && !orders && <p>Cargando...</p>}
        {orders && (
          <table>
            <thead>
              <tr>
                <th>N° OT</th>
                <th>Fecha</th>
                <th>Motivo</th>
                <th>Diagnóstico</th>
                <th>Trabajo realizado</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td><span className="badge">{o.numero}</span></td>
                  <td>{o.fecha}</td>
                  <td>{o.motivo || "—"}</td>
                  <td>{o.diagnostico || "—"}</td>
                  <td>{o.trabajo_realizado || "—"}</td>
                  <td>{o.estado}</td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>
                    No hay órdenes de servicio registradas todavía.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  );
}
