import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type CustomerRow = {
  id: string;
  nombre: string;
  rut: string | null;
  ciudad: string | null;
  contacto: string | null;
  telefono: string | null;
  tipo_cliente: string | null;
  estado: string;
};

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<CustomerRow[]>("/api/customers")
      .then(setCustomers)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de clientes.")
      );
  }, []);

  return (
    <Layout>
      <div className="card">
        <h2>Clientes</h2>
        {error && <div className="error-box">{error}</div>}
        {!error && !customers && <p>Cargando...</p>}
        {customers && (
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>RUT</th>
                <th>Ciudad</th>
                <th>Contacto</th>
                <th>Teléfono</th>
                <th>Tipo</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id}>
                  <td>{c.nombre}</td>
                  <td>{c.rut || "—"}</td>
                  <td>{c.ciudad || "—"}</td>
                  <td>{c.contacto || "—"}</td>
                  <td>{c.telefono || "—"}</td>
                  <td>{c.tipo_cliente || "—"}</td>
                  <td>{c.estado}</td>
                </tr>
              ))}
              {customers.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>
                    No hay clientes registrados todavía.
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
