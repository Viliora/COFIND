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
    <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-stone-200/60">
          <thead className="bg-stone-100/60">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-stone-500"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-stone-400">
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                    Memuat data...
                  </div>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-sm text-red-500">
                  {error}
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-stone-400">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr key={row.id || row.place_id || index} className="align-top hover:bg-stone-50 transition-colors duration-300 ease-out">
                  {columns.map((column) => (
                    <td key={column.key} className="px-4 py-3 text-sm text-stone-700">
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
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-stone-200/60 bg-stone-100/40">
          <p className="text-sm text-stone-400">
            Halaman <span className="font-semibold text-stone-700">{pagination.page}</span> dari {pagination.total_pages} &bull; <span className="font-semibold text-stone-700">{pagination.total}</span> data
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => onPageChange?.(pagination.page - 1)}
              className="rounded-lg px-3 py-1.5 text-sm bg-[#FAF9F6] border border-stone-300/60 text-stone-600 hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300 ease-out cursor-pointer"
            >
              ← Sebelumnya
            </button>
            <button
              type="button"
              disabled={pagination.page >= pagination.total_pages}
              onClick={() => onPageChange?.(pagination.page + 1)}
              className="rounded-lg px-3 py-1.5 text-sm bg-[#FAF9F6] border border-stone-300/60 text-stone-600 hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300 ease-out cursor-pointer"
            >
              Berikutnya →
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
