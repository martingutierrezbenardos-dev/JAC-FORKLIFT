import { useEffect, useState } from "react";
import BarList from "@/components/BarList";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type ReporteGastos = {
  periodo: { desde: string | null; hasta: string | null };
  total: number;
  cantidad_registros: number;
  por_categoria: Record<string, number>;
  por_sucursal: Record<string, number>;
  por_trabajador: Record<string, number>;
  pendiente_de_reembolso: number;
};

type ReporteServicios = {
  cantidad_registros: number;
  por_tecnico: Record<string, number>;
  por_estado: Record<string, number>;
  tiempo_promedio_atencion_horas: number | null;
  tiempo_promedio_traslado_horas: number | null;
};

type ReporteTareas = {
  cantidad_registros: number;
  por_estado: Record<string, number>;
};

type AlertaMantenimiento = {
  numero_interno: string;
  cliente: string | null;
  dias_restantes: number | null;
  horas_excedidas: number | null;
};

type ReporteMantenimiento = {
  cantidad: number;
  alertas: AlertaMantenimiento[];
};

const money = (v: number) => `$${v.toLocaleString("es-CL")}`;

export default function DashboardPage() {
  const [gastos, setGastos] = useState<ReporteGastos | null>(null);
  const [servicios, setServicios] = useState<ReporteServicios | null>(null);
  const [tareas, setTareas] = useState<ReporteTareas | null>(null);
  const [mantenimiento, setMantenimiento] = useState<ReporteMantenimiento | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiGet<ReporteGastos>("/api/reports/gastos?periodo=mes"),
      apiGet<ReporteServicios>("/api/reports/servicios"),
      apiGet<ReporteTareas>("/api/reports/tareas"),
      apiGet<ReporteMantenimiento>("/api/reports/mantenimiento-pendiente"),
    ])
      .then(([g, s, t, m]) => {
        setGastos(g);
        setServicios(s);
        setTareas(t);
        setMantenimiento(m);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar el dashboard.")
      );
  }, []);

  const tareasPendientes = tareas
    ? (tareas.por_estado["pendiente"] || 0) + (tareas.por_estado["en_progreso"] || 0)
    : null;

  return (
    <Layout>
      <h2 style={{ marginBottom: "1rem" }}>Dashboard</h2>
      {error && <div className="error-box">{error}</div>}

      <div className="stat-grid">
        <div className="stat-tile">
          <div className="stat-label">Gastos este mes</div>
          <div className="stat-value">{gastos ? money(gastos.total) : "—"}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Pendiente de reembolso</div>
          <div className="stat-value">{gastos ? money(gastos.pendiente_de_reembolso) : "—"}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Servicios registrados</div>
          <div className="stat-value">{servicios ? servicios.cantidad_registros : "—"}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Tareas pendientes</div>
          <div className="stat-value">{tareasPendientes ?? "—"}</div>
        </div>
        <div className={`stat-tile ${mantenimiento && mantenimiento.cantidad > 0 ? "stat-alert" : ""}`}>
          <div className="stat-label">Máquinas con mantenimiento pendiente</div>
          <div className="stat-value">{mantenimiento ? mantenimiento.cantidad : "—"}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Tiempo promedio de atención</div>
          <div className="stat-value">
            {servicios?.tiempo_promedio_atencion_horas != null
              ? `${servicios.tiempo_promedio_atencion_horas} h`
              : "—"}
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="card">
          <h3>Gastos por categoría (este mes)</h3>
          {gastos ? <BarList data={gastos.por_categoria} formatValue={money} /> : <p>Cargando...</p>}
        </div>
        <div className="card">
          <h3>Gastos por sucursal (este mes)</h3>
          {gastos ? <BarList data={gastos.por_sucursal} formatValue={money} /> : <p>Cargando...</p>}
        </div>
        <div className="card">
          <h3>Gastos por trabajador (este mes)</h3>
          {gastos ? <BarList data={gastos.por_trabajador} formatValue={money} /> : <p>Cargando...</p>}
        </div>
        <div className="card">
          <h3>Servicios por técnico</h3>
          {servicios ? <BarList data={servicios.por_tecnico} /> : <p>Cargando...</p>}
        </div>
        <div className="card">
          <h3>Servicios por estado</h3>
          {servicios ? <BarList data={servicios.por_estado} /> : <p>Cargando...</p>}
        </div>
        <div className="card">
          <h3>Mantenimientos atrasados o próximos</h3>
          {!mantenimiento && <p>Cargando...</p>}
          {mantenimiento && mantenimiento.alertas.length === 0 && (
            <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>Ninguna máquina tiene mantenimiento pendiente.</p>
          )}
          {mantenimiento && mantenimiento.alertas.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Máquina</th>
                  <th>Cliente</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {mantenimiento.alertas.map((a) => (
                  <tr key={a.numero_interno}>
                    <td><span className="badge">{a.numero_interno}</span></td>
                    <td>{a.cliente || "—"}</td>
                    <td>
                      {a.dias_restantes != null &&
                        (a.dias_restantes < 0
                          ? `Atrasada ${Math.abs(a.dias_restantes)} días`
                          : `En ${a.dias_restantes} días`)}
                      {a.dias_restantes == null && a.horas_excedidas != null &&
                        `Excedida por ${a.horas_excedidas} h`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Layout>
  );
}
