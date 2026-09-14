import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet, apiPost } from "@/lib/api";

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

const ROLES: { value: string; label: string }[] = [
  { value: "tecnico", label: "Técnico" },
  { value: "vendedor", label: "Vendedor" },
  { value: "administracion", label: "Administración" },
  { value: "jefe_servicios_tecnicos", label: "Jefe de Servicios Técnicos" },
  { value: "gerente_sucursal", label: "Gerente de Sucursal" },
  { value: "gerente_marketing", label: "Gerente de Marketing" },
  { value: "responsable_mercado_publico", label: "Responsable Mercado Público" },
  { value: "gerente_general", label: "Gerente General" },
  { value: "admin_sistema", label: "Administrador del Sistema" },
];

const emptyForm = {
  nombre: "",
  apellido: "",
  telefono_whatsapp: "",
  email: "",
  cargo: "",
  area: "",
  sucursal: "",
  rol: "tecnico",
  password: "",
};

export default function UsersPage() {
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function loadUsers() {
    apiGet<UserRow[]>("/api/users")
      .then(setUsers)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de usuarios.")
      );
  }

  useEffect(() => {
    loadUsers();
  }, []);

  function updateField(field: keyof typeof emptyForm, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSaving(true);
    try {
      await apiPost("/api/users", {
        nombre: form.nombre,
        apellido: form.apellido,
        telefono_whatsapp: form.telefono_whatsapp,
        email: form.email || null,
        cargo: form.cargo,
        area: form.area,
        sucursal: form.sucursal,
        rol: form.rol,
        password: form.password || null,
      });
      setForm(emptyForm);
      loadUsers();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo crear el usuario.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Layout>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h2>Agregar usuario</h2>
        <p style={{ color: "#6b7280", fontSize: "0.85rem", marginTop: -8 }}>
          El teléfono debe estar en formato internacional (ej. +56912345678) — es lo que el
          sistema usa para identificar a la persona por WhatsApp. La contraseña solo es
          necesaria si esta persona va a entrar al panel web (gerencia, administración); un
          técnico que solo use WhatsApp puede dejarla en blanco.
        </p>
        {formError && <div className="error-box">{formError}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div className="field">
              <label htmlFor="nombre">Nombre</label>
              <input id="nombre" required value={form.nombre} onChange={(e) => updateField("nombre", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="apellido">Apellido</label>
              <input id="apellido" required value={form.apellido} onChange={(e) => updateField("apellido", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="telefono">Teléfono WhatsApp</label>
              <input
                id="telefono"
                required
                placeholder="+56912345678"
                pattern="^\+\d{8,15}$"
                value={form.telefono_whatsapp}
                onChange={(e) => updateField("telefono_whatsapp", e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="email">Email (opcional, requerido para acceso al panel)</label>
              <input id="email" type="email" value={form.email} onChange={(e) => updateField("email", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="rol">Rol</label>
              <select id="rol" value={form.rol} onChange={(e) => updateField("rol", e.target.value)}>
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sucursal">Sucursal</label>
              <input id="sucursal" value={form.sucursal} onChange={(e) => updateField("sucursal", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="cargo">Cargo</label>
              <input id="cargo" value={form.cargo} onChange={(e) => updateField("cargo", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="area">Área</label>
              <input id="area" value={form.area} onChange={(e) => updateField("area", e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="password">Contraseña panel web (opcional)</label>
              <input
                id="password"
                type="password"
                minLength={8}
                placeholder="mínimo 8 caracteres, dejar vacío si no usa el panel"
                value={form.password}
                onChange={(e) => updateField("password", e.target.value)}
              />
            </div>
          </div>
          <button className="btn" type="submit" disabled={saving} style={{ marginTop: "1rem" }}>
            {saving ? "Guardando..." : "Crear usuario"}
          </button>
        </form>
      </div>

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
