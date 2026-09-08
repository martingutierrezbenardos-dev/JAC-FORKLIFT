import { useEffect, useState } from "react";
import BarList from "@/components/BarList";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type Variacion = { absoluta: number; porcentaje: number | null };

type AlertaMantenimiento = {
  numero_interno: string;
  cliente: string | null;
  dias_restantes: number | null;
  horas_excedidas: number | null;
};

type ContratoGrua = {
  cliente: string | null;
  porcentaje_usado: number;
  horas_disponibles: number;
};

type ResumenEjecutivo = {
  periodo: { desde: string; hasta: string };
  periodo_anterior: { desde: string; hasta: string };
  gastos: {
    total: number;
    variacion_vs_periodo_anterior: Variacion;
    pendiente_de_reembolso: number;
    por_categoria: Record<string, number>;
  };
  tareas: { cantidad: number; completadas: number; por_estado: Record<string, number> };
  servicios: { cantidad: number; cerrados: number; tiempo_promedio_atencion_horas: number | null };
  mantenimiento: { maquinas_con_alerta: number; detalle: AlertaMantenimiento[] };
  gruas: { contratos_por_agotarse: number; detalle: ContratoGrua[] };
};

const money = (v: number) => `$${v.toLocaleString("es-CL")}`;

function formatVariacion(v: Variacion): string {
  const signo = v.absoluta > 0 ? "+" : "";
  const monto = `${signo}${money(v.absoluta)}`;
  if (v.porcentaje === null) return monto;
  return `${monto} (${signo}${v.porcentaje}%)`;
}

export default function ResumenEjecutivoPage() {
  const [resumen, setResumen] = useState<ResumenEjecutivo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sinPermiso, setSinPermiso] = useState(false);

  useEffect(() => {
    apiGet<ResumenEjecutivo>("/api/reports/resumen-ejecutivo?periodo=mes")
      .then(setResumen)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setSinPermiso(true);
          return;
        }
        setError(err instanceof ApiError ? err.message : "No se pudo cargar el resumen ejecutivo.");
      });
  }, []);

  if (sinPermiso) {
    return (
      <Layout>
        <div className="card">
          <h2>Resumen ejecutivo</h2>
          <p style={{ color: "#6b7280" }}>
            Esta sección muestra información agregada de toda la empresa y requiere permisos de
            administración o gerencia. Tu rol actual no tiene acceso.
          </p>
        </div>
      </Layout>
    );
  }

  const variacionPositiva = resumen ? resumen.gastos.variacion_vs_periodo_anterior.absoluta >= 0 : null;

  return (
    <Layout>
      <h2 style={{ marginBottom: "0.25rem" }}>Resumen ejecutivo</h2>
      {resumen && (
        <p style={{ color: "#6b7280", marginTop: 0, marginBottom: "1rem" }}>
          Período: {resumen.periodo.desde} → {resumen.periodo.hasta} (comparado con {resumen.periodo_anterior.desde} → {resumen.periodo_anterior.hasta})
        </p>
      )}
      {error && <div className="error-box">{error}</div>}

      <div className="stat-grid">
        <div className="stat-tile">
          <div className="stat-label">Gastos del período</div>
          <div className="stat-value">{resumen ? money(resumen.gastos.total) : "—"}</div>
        </div>
        <div className={`stat-tile ${resumen && variacionPositiva ? "stat-alert" : ""}`}>
          <div className="stat-label">Variación vs. período anterior</div>
          <div className="stat-value">
            {resumen ? formatVariacion(resumen.gastos.variacion_vs_periodo_anterior) : "—"}
          </div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Tareas completadas</div>
          <div className="stat-value">
            {resumen ? `${resumen.tareas.completadas} / ${resumen.tareas.cantidad}` : "—"}
          </div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Servicios cerrados</div>
          <div className="stat-value">
            {resumen ? `${resumen.servicios.cerrados} / ${resumen.servicios.cantidad}` : "—"}
          </div>
        </div>
        <div className={`stat-tile ${resumen && resumen.mantenimiento.maquinas_con_alerta > 0 ? "stat-alert" : ""}`}>
          <div className="stat-label">Máquinas con mantenimiento pendiente</div>
          <div className="stat-value">{resumen ? resumen.mantenimiento.maquinas_con_alerta : "—"}</div>
        </div>
        <div className={`stat-tile ${resumen && resumen.gruas.contratos_por_agotarse > 0 ? "stat-alert" : ""}`}>
          <div className="stat-label">Contratos de grúa por agotarse</div>
          <div className="stat-value">{resumen ? resumen.gruas.contratos_por_agotarse : "—"}</div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="card">
          <h3>Gastos por categoría</h3>
          {resumen ? <BarList data={resumen.gastos.por_categoria} formatValue={money} /> : <p>Cargando...</p>}
        </div>
        <div className="card">
          <h3>Máquinas con mantenimiento pendiente</h3>
          {resumen && resumen.mantenimiento.detalle.length === 0 && (
            <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>Ninguna.</p>
          )}
          {resumen && resumen.mantenimiento.detalle.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Máquina</th>
                  <th>Cliente</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {resumen.mantenimiento.detalle.map((a) => (
                  <tr key={a.numero_interno}>
                    <td><span className="badge">{a.numero_interno}</span></td>
                    <td>{a.cliente || "—"}</td>
                    <td>
                      {a.dias_restantes != null &&
                        (a.dias_restantes < 0
                          ? `Atrasada ${Math.abs(a.dias_restantes)} días`
                          : `En ${a.dias_restantes} días`)}
                      {a.dias_restantes == null && a.horas_excedidas != null && `Excedida por ${a.horas_excedidas} h`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!resumen && <p>Cargando...</p>}
        </div>
        <div className="card">
          <h3>Contratos de grúa por agotarse (≥85% usado)</h3>
          {resumen && resumen.gruas.detalle.length === 0 && (
            <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>Ninguno.</p>
          )}
          {resumen && resumen.gruas.detalle.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>% usado</th>
                  <th>Horas disponibles</th>
                </tr>
              </thead>
              <tbody>
                {resumen.gruas.detalle.map((c, i) => (
                  <tr key={i}>
                    <td>{c.cliente || "—"}</td>
                    <td>{c.porcentaje_usado}%</td>
                    <td>{c.horas_disponibles}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!resumen && <p>Cargando...</p>}
        </div>
      </div>
    </Layout>
  );
}
