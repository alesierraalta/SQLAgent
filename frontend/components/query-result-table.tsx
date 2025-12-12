type QueryResultTableProps = {
  columns?: string[] | null;
  rows?: Array<Record<string, unknown>> | null;
};

export function QueryResultTable({ columns, rows }: QueryResultTableProps) {
  if (!rows || rows.length === 0) return null;

  const resolvedColumns =
    columns && columns.length > 0 ? columns : Array.from(new Set(rows.flatMap((row) => Object.keys(row))));

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="min-w-full text-sm">
        <thead className="bg-neutral-900 text-neutral-200">
          <tr>
            {resolvedColumns.map((col) => (
              <th key={col} className="px-3 py-2 text-left font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className="border-t border-neutral-800">
              {resolvedColumns.map((col) => (
                <td key={col} className="px-3 py-2 text-neutral-100">
                  {String(row[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

