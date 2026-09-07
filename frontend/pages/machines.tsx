import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type MachineRow = {
  id: string;
  numero_interno: string;
  marca: string | null;
  modelo: string | null;
  tipo: string | null;
  horometro: number | null;
  estado: string;
  ubicacion: string | null;
};

export default function MachinesPage() {
  const [machines, setMachines] = useState<MachineRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<MachineRow[]>("/api/machines")
      .then(setMachines)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de máquinas.")
      );
  }, []);

  return (
    <Layout>
      <div className="card">
        <h2>Máquinas</h2>
        {error && <div className="error-box">{error}</div>}
        {!error && !machines && <p>Cargando...</p>}
        {machines && (
          <table>
            <thead>
              <tr>
                <th>N° interno</th>
                <th>Marca</th>
                <th>Modelo</th>
                <th>Tipo</th>
                <th>Horómetro</th>
                <th>Estado</th>
                <th>Ubicación</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((m) => (
                <tr key={m.id}>
                  <td><span className="badge">{m.numero_interno}</span></td>
                  <td>{m.marca || "—"}</td>
                  <td>{m.modelo || "—"}</td>
                  <td>{m.tipo || "—"}</td>
                  <td>{m.horometro ?? "—"}</td>
                  <td>{m.estado}</td>
                  <td>{m.ubicacion || "—"}</td>
                </tr>
              ))}
              {machines.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>
                    No hay máquinas registradas todavía.
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
