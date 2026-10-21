import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  /** Right-align numeric columns (money, counts). */
  align?: 'left' | 'right'
  className?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  caption: string
  onRowClick?: (row: T) => void
  minWidth?: string
}

/**
 * Responsive table: the table scrolls horizontally inside its own container so the page
 * itself never overflows on small screens.
 */
export function DataTable<T>({ columns, rows, rowKey, caption, onRowClick, minWidth = '40rem' }: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={caption}>
      <table className="type-table w-full border-collapse text-left" style={{ minWidth }}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line bg-page">
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={cn(
                  'type-label px-4 py-3 whitespace-nowrap text-muted',
                  col.align === 'right' && 'text-right',
                  col.className,
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={cn('border-b border-line last:border-0', onRowClick && 'cursor-pointer hover:bg-page')}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn('px-4 py-3 align-middle', col.align === 'right' && 'text-right tabular', col.className)}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
