import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet, apiPost } from "@/lib/api";

type TaskRow = {
  id: string;
  titulo: string;
  descripcion: string | null;
  fecha_limite: string | null;
  prioridad: string;
  estado: string;
  proyecto: string | null;
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function reload() {
    apiGet<TaskRow[]>("/api/tasks")
      .then(setTasks)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de tareas.")
      );
  }

  useEffect(reload, []);

  async function completar(taskId: string) {
    setBusyId(taskId);
    try {
      await apiPost(`/api/tasks/${taskId}/completar`, {});
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo completar la tarea.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Layout>
      <div className="card">
        <h2>Tareas</h2>
        {error && <div className="error-box">{error}</div>}
        {!error && !tasks && <p>Cargando...</p>}
        {tasks && (
          <table>
            <thead>
              <tr>
                <th>Título</th>
                <th>Prioridad</th>
                <th>Fecha límite</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id}>
                  <td>{t.titulo}</td>
                  <td><span className="badge">{t.prioridad}</span></td>
                  <td>{t.fecha_limite ? new Date(t.fecha_limite).toLocaleString("es-CL") : "—"}</td>
                  <td>{t.estado}</td>
                  <td>
                    {t.estado !== "completada" && t.estado !== "cancelada" && (
                      <button
                        className="btn btn-secondary"
                        disabled={busyId === t.id}
                        onClick={() => completar(t.id)}
                      >
                        Completar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {tasks.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", color: "#6b7280" }}>
                    No hay tareas registradas todavía.
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
