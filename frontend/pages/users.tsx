import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type UserRow = {
  id: string;
  nombre: string;
  apellido: string;
  telefono_whatsapp: string;
  email: string | null;
  cargo: string;
  sucursal: string;
  rol: string;
  activo: boolean;
};

export default function UsersPage() {
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<UserRow[]>("/api/users")
      .then(setUsers)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de usuarios.")
      );
  }, []);

  return (
    <Layout>
      <div className="card">
        <h2>Usuarios</h2>
        {error && <div className="error-box">{error}</div>}
        {!error && !users && <p>Cargando...</p>}
        {users && (
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Teléfono WhatsApp</th>
                <th>Email</th>
                <th>Cargo</th>
                <th>Sucursal</th>
                <th>Rol</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.nombre} {u.apellido}</td>
                  <td>{u.telefono_whatsapp}</td>
                  <td>{u.email || "—"}</td>
                  <td>{u.cargo}</td>
                  <td>{u.sucursal}</td>
                  <td><span className="badge">{u.rol}</span></td>
                  <td>{u.activo ? "Activo" : "Inactivo"}</td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>
                    No hay usuarios registrados todavía.
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
