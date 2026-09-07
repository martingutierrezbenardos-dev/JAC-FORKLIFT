type BarListProps = {
  data: Record<string, number>;
  maxItems?: number;
  formatValue?: (value: number) => string;
};

export default function BarList({ data, maxItems = 8, formatValue }: BarListProps) {
  const entries = Object.entries(data)
    .sort((a, b) => b[1] - a[1])
    .slice(0, maxItems);

  if (entries.length === 0) {
    return <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>Sin datos en este período.</p>;
  }

  const max = Math.max(...entries.map(([, v]) => v), 1);
  const format = formatValue || ((v: number) => v.toLocaleString("es-CL"));

  return (
    <div className="bar-list">
      {entries.map(([label, value]) => (
        <div className="bar-row" key={label}>
          <span className="bar-label" title={label}>{label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(value / max) * 100}%` }} />
          </div>
          <span className="bar-value">{format(value)}</span>
        </div>
      ))}
    </div>
  );
}
