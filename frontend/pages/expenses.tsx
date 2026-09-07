import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { ApiError, apiGet } from "@/lib/api";

type ExpenseRow = {
  id: string;
  fecha: string;
  monto: string;
  moneda: string;
  categoria: string;
  proveedor: string | null;
  descripcion: string | null;
  forma_pago: string;
  requiere_reembolso: boolean;
  estado_reembolso: string | null;
};

export default function ExpensesPage() {
  const [expenses, setExpenses] = useState<ExpenseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ExpenseRow[]>("/api/expenses")
      .then(setExpenses)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista de gastos.")
      );
  }, []);

  const total = expenses?.reduce((acc, e) => acc + Number(e.monto), 0) ?? 0;

  return (
    <Layout>
      <div className="card">
        <h2>Gastos</h2>
        <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>
          Solo se muestran los gastos que tu rol tiene permiso de ver (propios, o de toda la
          empresa si tienes ese permiso).
        </p>
        {error && <div className="error-box">{error}</div>}
        {!error && !expenses && <p>Cargando...</p>}
        {expenses && (
          <>
            <p><strong>Total mostrado:</strong> ${total.toLocaleString("es-CL")}</p>
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Categoría</th>
                  <th>Monto</th>
                  <th>Proveedor</th>
                  <th>Forma de pago</th>
                  <th>Reembolso</th>
                </tr>
              </thead>
              <tbody>
                {expenses.map((e) => (
                  <tr key={e.id}>
                    <td>{e.fecha}</td>
                    <td><span className="badge">{e.categoria}</span></td>
                    <td>${Number(e.monto).toLocaleString("es-CL")} {e.moneda}</td>
                    <td>{e.proveedor || "—"}</td>
                    <td>{e.forma_pago}</td>
                    <td>{e.requiere_reembolso ? (e.estado_reembolso || "pendiente") : "—"}</td>
                  </tr>
                ))}
                {expenses.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>
                      No hay gastos registrados todavía.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </>
        )}
      </div>
    </Layout>
  );
}
