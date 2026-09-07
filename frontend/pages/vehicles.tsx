import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type VehicleRow = {
  id: string;
  patente: string;
  marca: string | null;
  modelo: string | null;
  anio: number | null;
  sucursal: string | null;
  estado: string;
  observaciones: string | null;
};

export default function VehiclesPage() {
  const [vehicles, setVehicles] = useState<VehicleRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<VehicleRow[]>("/api/vehicles")
      .then(setVehicles)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de vehículos.")
      );
  }, []);

  return (
    <Layout>
      <div className="card">
        <h2>Vehículos</h2>
        <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>
          Fichas de la flota. La ubicación en vivo y el kilometraje dependen de un proveedor
          de GPS que todavía no está configurado (ver docs/architecture.md).
        </p>
        {error && <div className="error-box">{error}</div>}
        {!error && !vehicles && <p>Cargando...</p>}
        {vehicles && (
          <table>
            <thead>
              <tr>
                <th>Patente</th>
                <th>Marca</th>
                <th>Modelo</th>
                <th>Año</th>
                <th>Sucursal</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((v) => (
                <tr key={v.id}>
                  <td><span className="badge">{v.patente}</span></td>
                  <td>{v.marca || "—"}</td>
                  <td>{v.modelo || "—"}</td>
                  <td>{v.anio ?? "—"}</td>
                  <td>{v.sucursal || "—"}</td>
                  <td>{v.estado}</td>
                </tr>
              ))}
              {vehicles.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>
                    No hay vehículos registrados todavía.
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
