/**
 * Enhanced Data Table Component for Data Analyst
 * Uses Eliza Forge Design System components
 * Scrollable table with sorting, filtering, pagination, and export
 */
import React, { useMemo, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  ColumnDef,
  SortingState,
} from '@tanstack/react-table';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpDownIcon,
  ArrowDownTrayIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import * as XLSX from 'xlsx';
import { cn } from '../../shared/lib/cn';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

interface DataTableProps {
  data: {
    columns: string[];
    rows: any[][];
    row_count: number;
  };
}

export default function DataTable({ data }: DataTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 10;

  // Transform data into table format
  const tableData = useMemo(() => {
    return data.rows.map((row, index) => {
      const obj: Record<string, any> = { _id: index };
      data.columns.forEach((col, idx) => {
        obj[col] = row[idx];
      });
      return obj;
    });
  }, [data]);

  // Define columns with enhanced formatting
  const columns = useMemo<ColumnDef<any>[]>(() => {
    return data.columns.map((col) => ({
      accessorKey: col,
      header: col,
      cell: ({ getValue }) => {
        const value = getValue();
        
        // Handle null/undefined
        if (value === null || value === undefined) {
          return <span className="text-gray-400 dark:text-gray-500 text-xs">—</span>;
        }
        
        // Format numbers
        if (typeof value === 'number') {
          const formatted = Number.isInteger(value)
            ? value.toLocaleString('en-US')
            : value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          return <span className="font-mono text-sm">{formatted}</span>;
        }
        
        // Format booleans
        if (typeof value === 'boolean') {
          return (
            <span className={cn(
              "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
              value 
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' 
                : 'bg-gray-100 text-gray-700 dark:bg-dark-surface-2 dark:text-gray-300'
            )}>
              <span className={cn(
                "w-1.5 h-1.5 rounded-full",
                value ? "bg-green-500" : "bg-gray-400"
              )} />
              {value ? 'Yes' : 'No'}
            </span>
          );
        }
        
        // Format dates (ISO string detection)
        const str = String(value);
        if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
          try {
            const date = new Date(str);
            if (!isNaN(date.getTime())) {
              return (
                <span className="text-gray-600 dark:text-gray-300 text-sm">
                  {date.toLocaleDateString('en-US', { 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric' 
                  })}
                </span>
              );
            }
          } catch {
            // Not a valid date, fall through
          }
        }
        
        // Format long strings with truncation
        if (str.length > 50) {
          return (
            <span className="text-sm text-charcoal dark:text-white" title={str}>
              {str.substring(0, 47)}...
            </span>
          );
        }
        
        return <span className="text-sm text-charcoal dark:text-white">{str}</span>;
      },
    }));
  }, [data.columns]);

  const table = useReactTable({
    data: tableData,
    columns,
    state: {
      sorting,
      globalFilter,
      pagination: {
        pageSize,
        pageIndex: page - 1,
      },
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const totalPages = table.getPageCount();
  const totalItems = tableData.length;

  // Export functions
  const exportToCSV = () => {
    const csv = [
      data.columns.join(','),
      ...data.rows.map((row) =>
        row.map((cell) => {
          const str = String(cell ?? '');
          return str.includes(',') ? `"${str}"` : str;
        }).join(',')
      ),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `data-export-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const exportToExcel = () => {
    const ws = XLSX.utils.aoa_to_sheet([data.columns, ...data.rows]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Data');
    XLSX.writeFile(wb, `data-export-${new Date().toISOString().split('T')[0]}.xlsx`);
  };

  const exportToJSON = () => {
    const json = JSON.stringify(tableData, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `data-export-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500 dark:text-gray-400">
        <p className="text-sm">No data to display</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col min-w-0 space-y-4">
      {/* Controls Bar */}
      <div className="flex items-center justify-between gap-4">
        {/* Search Input - DS Input */}
        <div className="relative flex-1 max-w-sm">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            type="text"
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder="Filter data..."
            className="pl-10"
          />
        </div>
        
        {/* Export Buttons - DS Button */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={exportToCSV}>
            <ArrowDownTrayIcon className="w-4 h-4 mr-1.5" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={exportToExcel}>
            <ArrowDownTrayIcon className="w-4 h-4 mr-1.5" />
            Excel
          </Button>
          <Button variant="outline" size="sm" onClick={exportToJSON}>
            <ArrowDownTrayIcon className="w-4 h-4 mr-1.5" />
            JSON
          </Button>
        </div>
      </div>

      {/* Table Container - DS styled */}
      <div className={cn(
        "relative overflow-auto rounded-lg flex-1 min-w-0",
        "border border-gray-200 dark:border-dark-border/50",
        "bg-white dark:bg-dark-surface"
      )}>
        <table className="min-w-max border-collapse">
          {/* Header */}
          <thead className="bg-gray-50 dark:bg-dark-surface-2 sticky top-0 z-10">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const isSorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className={cn(
                        "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider",
                        "text-gray-500 dark:text-gray-400",
                        "cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200",
                        "transition-colors"
                      )}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <div className="flex items-center gap-1">
                        <span>{flexRender(header.column.columnDef.header, header.getContext())}</span>
                        <span className="flex-shrink-0">
                          {isSorted === 'asc' ? (
                            <ChevronUpIcon className="w-4 h-4 text-eliza-red" />
                          ) : isSorted === 'desc' ? (
                            <ChevronDownIcon className="w-4 h-4 text-eliza-red" />
                          ) : (
                            <ChevronUpDownIcon className="w-4 h-4 opacity-40" />
                          )}
                        </span>
                      </div>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          
          {/* Body */}
          <tbody className="divide-y divide-gray-200 dark:divide-dark-border/50">
            {table.getRowModel().rows.map((row, rowIndex) => (
              <tr
                key={row.id}
                className={cn(
                  "transition-colors",
                  "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
                  rowIndex % 2 === 1 && "bg-gray-50/50 dark:bg-dark-surface-2/30"
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="px-4 py-3 text-sm text-charcoal dark:text-white"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination - DS styled */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, totalItems)} of {totalItems} results
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className={cn(
                "flex items-center justify-center w-8 h-8 rounded-full",
                "border border-gray-200 dark:border-dark-border/50",
                "bg-white dark:bg-dark-surface",
                "text-gray-500 dark:text-gray-400",
                "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "transition-colors"
              )}
              aria-label="Previous page"
            >
              <ChevronLeftIcon className="w-4 h-4" />
            </button>
            
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
                let pageNum: number;
                
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (page <= 3) {
                  pageNum = i + 1;
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = page - 2 + i;
                }
                
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={cn(
                      "flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium",
                      "transition-colors",
                      page === pageNum
                        ? "bg-eliza-red text-white"
                        : "border border-gray-200 dark:border-dark-border/50 bg-white dark:bg-dark-surface text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-surface-2"
                    )}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>
            
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className={cn(
                "flex items-center justify-center w-8 h-8 rounded-full",
                "border border-gray-200 dark:border-dark-border/50",
                "bg-white dark:bg-dark-surface",
                "text-gray-500 dark:text-gray-400",
                "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "transition-colors"
              )}
              aria-label="Next page"
            >
              <ChevronRightIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
