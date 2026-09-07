import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type CraneContractRow = {
  id: string;
  cliente: string | null;
  periodo_inicio: string;
  periodo_fin: string;
  horas_contratadas: number;
  horas_utilizadas: number;
  horas_disponibles: number;
  porcentaje_usado: number;
  alerta: boolean;
  estado: string;
};

export default function CranesPage() {
  const [contracts, setContracts] = useState<CraneContractRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<CraneContractRow[]>("/api/crane-contracts")
      .then(setContracts)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar los contratos de grúa.")
      );
  }, []);

  return (
    <Layout>
      <div className="card">
        <h2>Contratos de grúa</h2>
        {error && <div className="error-box">{error}</div>}
        {!error && !contracts && <p>Cargando...</p>}
        {contracts && (
          <table>
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Período</th>
                <th>Horas contratadas</th>
                <th>Horas usadas</th>
                <th>Disponibles</th>
                <th>% usado</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((c) => (
                <tr key={c.id} style={c.alerta ? { background: "#fff7ed" } : undefined}>
                  <td>{c.cliente || "—"}</td>
                  <td>{c.periodo_inicio} → {c.periodo_fin}</td>
                  <td>{c.horas_contratadas}</td>
                  <td>{c.horas_utilizadas}</td>
                  <td>{c.horas_disponibles}</td>
                  <td>
                    {c.porcentaje_usado}%
                    {c.alerta && <span className="badge" style={{ marginLeft: 6, background: "#fef3c7" }}>alerta</span>}
                  </td>
                </tr>
              ))}
              {contracts.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>
                    No hay contratos de grúa activos.
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
