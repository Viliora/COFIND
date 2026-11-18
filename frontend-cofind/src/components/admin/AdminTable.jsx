import React from 'react';

export default function AdminTable({
  columns,
  rows,
  loading,
  error,
  emptyMessage = 'Tidak ada data.',
  pagination,
  onPageChange,
}) {
  return (
    <div className="overflow-hidden rounded-panel border border-cofind-rule bg-cofind-surface shadow-cofind-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-cofind-rule">
          <thead className="bg-cofind-paper">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-cofind-muted ${
                    column.align === 'center' ? 'text-center' : 'text-left'
                  }`}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-cofind-rule">
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-cofind-muted">
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-cofind-rule border-t-cofind-primary" />
                    Memuat data...
                  </div>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-sm text-red-600">
                  {error}
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-cofind-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr key={row.id || row.place_id || index} className="align-top transition-colors duration-200 hover:bg-cofind-paper">
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={`px-4 py-3 text-sm text-cofind-ink ${
                        column.align === 'center' ? 'text-center' : ''
                      }`}
                    >
                      {column.render ? column.render(row) : row[column.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination ? (
        <div className="flex items-center justify-between gap-3 border-t border-cofind-rule bg-cofind-paper px-4 py-3">
          <p className="text-sm text-cofind-muted">
            Halaman <span className="font-semibold text-cofind-ink">{pagination.page}</span> dari{' '}
            {pagination.total_pages} &bull;{' '}
            <span className="font-semibold text-cofind-ink">{pagination.total}</span> data
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => onPageChange?.(pagination.page - 1)}
              className="cursor-pointer rounded-control border border-cofind-rule bg-cofind-surface px-3 py-1.5 text-sm text-cofind-ink transition-colors duration-200 hover:bg-cofind-paper disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← Sebelumnya
            </button>
            <button
              type="button"
              disabled={pagination.page >= pagination.total_pages}
              onClick={() => onPageChange?.(pagination.page + 1)}
              className="cursor-pointer rounded-control border border-cofind-rule bg-cofind-surface px-3 py-1.5 text-sm text-cofind-ink transition-colors duration-200 hover:bg-cofind-paper disabled:cursor-not-allowed disabled:opacity-40"
            >
              Berikutnya →
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}