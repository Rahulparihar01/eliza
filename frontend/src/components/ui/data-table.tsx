/**
 * DataTable Component
 * 
 * A flexible, feature-rich data table component for displaying tabular data.
 * Supports sorting, pagination, row selection, expandable rows, custom cell rendering, and more.
 */

import * as React from "react"
import { 
  ChevronUpIcon, 
  ChevronDownIcon, 
  ChevronLeftIcon, 
  ChevronRightIcon,
  ChevronUpDownIcon,
} from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"
import { Checkbox } from "./checkbox"
import { Skeleton } from "./skeleton"

/* ===========================================
   Types
   =========================================== */

export interface Column<T> {
  /** Unique identifier for the column */
  id: string
  /** Column header text */
  header: string | React.ReactNode
  /** Accessor function or key to get the cell value */
  accessorKey?: keyof T
  /** Custom accessor function */
  accessorFn?: (row: T) => React.ReactNode
  /** Custom cell renderer */
  cell?: (props: { row: T; value: any }) => React.ReactNode
  /** Enable sorting for this column */
  sortable?: boolean
  /** Column width (CSS value) */
  width?: string
  /** Minimum width */
  minWidth?: string
  /** Text alignment */
  align?: "left" | "center" | "right"
  /** Hide on mobile */
  hideOnMobile?: boolean
  /** Custom header className */
  headerClassName?: string
  /** Custom cell className */
  cellClassName?: string
}

export type SortDirection = "asc" | "desc" | null

export interface SortState {
  column: string | null
  direction: SortDirection
}

export interface DataTableProps<T> {
  /** Array of data to display */
  data: T[]
  /** Column definitions */
  columns: Column<T>[]
  /** Unique key for each row */
  getRowId?: (row: T) => string | number
  /** Loading state */
  loading?: boolean
  /** Number of skeleton rows to show when loading */
  loadingRows?: number
  /** Empty state message */
  emptyMessage?: string
  /** Empty state icon */
  emptyIcon?: React.ReactNode
  /** Custom empty state content */
  emptyContent?: React.ReactNode
  /** Enable row selection */
  selectable?: boolean
  /** Selected row IDs */
  selectedRows?: Set<string | number>
  /** Selection change handler */
  onSelectionChange?: (selectedIds: Set<string | number>) => void
  /** Enable sorting */
  sortable?: boolean
  /** Current sort state */
  sortState?: SortState
  /** Sort change handler */
  onSortChange?: (sortState: SortState) => void
  /** Enable pagination */
  paginated?: boolean
  /** Current page (1-indexed) */
  page?: number
  /** Page size */
  pageSize?: number
  /** Total items (for server-side pagination) */
  totalItems?: number
  /** Page change handler */
  onPageChange?: (page: number) => void
  /** Row click handler */
  onRowClick?: (row: T) => void
  /** Row className function */
  rowClassName?: (row: T) => string
  /** Sticky header */
  stickyHeader?: boolean
  /** Max height (enables scroll) */
  maxHeight?: string
  /** Compact mode */
  compact?: boolean
  /** Striped rows */
  striped?: boolean
  /** Bordered cells */
  bordered?: boolean
  /** Hoverable rows */
  hoverable?: boolean
  /** Additional className */
  className?: string
  
  /* ===========================================
     Expandable Row Props
     =========================================== */
  
  /** Enable expandable rows */
  expandable?: boolean
  /** Render function for expanded row content */
  renderExpandedRow?: (row: T) => React.ReactNode
  /** Controlled expanded row IDs (if provided, expansion is controlled) */
  expandedRows?: Set<string | number>
  /** Callback when expansion changes (for controlled mode) */
  onExpandedChange?: (expandedIds: Set<string | number>) => void
  /** Allow multiple rows to be expanded at once (default: true) */
  allowMultipleExpanded?: boolean
  /** Default expanded row IDs (for uncontrolled mode) */
  defaultExpandedRows?: Set<string | number>
}

/* ===========================================
   DataTable Component
   =========================================== */

export function DataTable<T>({
  data,
  columns,
  getRowId = (row: any) => row.id,
  loading = false,
  loadingRows = 5,
  emptyMessage = "No data available",
  emptyIcon,
  emptyContent,
  selectable = false,
  selectedRows = new Set(),
  onSelectionChange,
  sortable = false,
  sortState = { column: null, direction: null },
  onSortChange,
  paginated = false,
  page = 1,
  pageSize = 10,
  totalItems,
  onPageChange,
  onRowClick,
  rowClassName,
  stickyHeader = false,
  maxHeight,
  compact = false,
  striped = false,
  bordered = false,
  hoverable = true,
  className,
  // Expandable props
  expandable = false,
  renderExpandedRow,
  expandedRows: controlledExpandedRows,
  onExpandedChange,
  allowMultipleExpanded = true,
  defaultExpandedRows = new Set(),
}: DataTableProps<T>) {
  
  // Expandable state (uncontrolled mode)
  const [internalExpandedRows, setInternalExpandedRows] = React.useState<Set<string | number>>(defaultExpandedRows)
  
  // Determine if controlled or uncontrolled
  const isExpandedControlled = controlledExpandedRows !== undefined
  const expandedRowIds = isExpandedControlled ? controlledExpandedRows : internalExpandedRows
  
  const handleToggleExpand = (rowId: string | number) => {
    const newExpanded = new Set(expandedRowIds)
    
    if (newExpanded.has(rowId)) {
      newExpanded.delete(rowId)
    } else {
      if (!allowMultipleExpanded) {
        newExpanded.clear()
      }
      newExpanded.add(rowId)
    }
    
    if (isExpandedControlled) {
      onExpandedChange?.(newExpanded)
    } else {
      setInternalExpandedRows(newExpanded)
    }
  }
  
  // Calculate pagination
  const totalPages = totalItems 
    ? Math.ceil(totalItems / pageSize) 
    : Math.ceil(data.length / pageSize)
  
  const paginatedData = paginated && !totalItems
    ? data.slice((page - 1) * pageSize, page * pageSize)
    : data
  
  const displayData = loading ? [] : paginatedData

  // Handle select all
  const allSelected = displayData.length > 0 && displayData.every(row => selectedRows.has(getRowId(row)))
  const someSelected = displayData.some(row => selectedRows.has(getRowId(row))) && !allSelected

  const handleSelectAll = () => {
    if (!onSelectionChange) return
    
    if (allSelected) {
      // Deselect all visible rows
      const newSelection = new Set(selectedRows)
      displayData.forEach(row => newSelection.delete(getRowId(row)))
      onSelectionChange(newSelection)
    } else {
      // Select all visible rows
      const newSelection = new Set(selectedRows)
      displayData.forEach(row => newSelection.add(getRowId(row)))
      onSelectionChange(newSelection)
    }
  }

  const handleSelectRow = (row: T) => {
    if (!onSelectionChange) return
    
    const id = getRowId(row)
    const newSelection = new Set(selectedRows)
    
    if (newSelection.has(id)) {
      newSelection.delete(id)
    } else {
      newSelection.add(id)
    }
    
    onSelectionChange(newSelection)
  }

  const handleSort = (columnId: string) => {
    if (!onSortChange) return
    
    let newDirection: SortDirection = "asc"
    
    if (sortState.column === columnId) {
      if (sortState.direction === "asc") {
        newDirection = "desc"
      } else if (sortState.direction === "desc") {
        newDirection = null
      }
    }
    
    onSortChange({
      column: newDirection ? columnId : null,
      direction: newDirection,
    })
  }

  const getCellValue = (row: T, column: Column<T>): any => {
    if (column.accessorFn) {
      return column.accessorFn(row)
    }
    if (column.accessorKey) {
      return row[column.accessorKey]
    }
    return null
  }

  const renderCell = (row: T, column: Column<T>) => {
    const value = getCellValue(row, column)
    
    if (column.cell) {
      return column.cell({ row, value })
    }
    
    return value
  }

  // Cell padding based on compact mode
  const cellPadding = compact ? "px-3 py-2" : "px-4 py-3"
  const headerPadding = compact ? "px-3 py-2" : "px-4 py-3"

  return (
    <div className={cn("w-full", className)}>
      {/* Table Container */}
      <div 
        className={cn(
          "relative overflow-auto rounded-lg border border-gray-200 dark:border-dark-border/50",
          "bg-white dark:bg-dark-surface"
        )}
        style={{ maxHeight }}
      >
        <table className="w-full border-collapse">
          {/* Header */}
          <thead 
            className={cn(
              "bg-gray-50 dark:bg-dark-surface-2",
              stickyHeader && "sticky top-0 z-10"
            )}
          >
            <tr>
              {/* Expand toggle column */}
              {expandable && (
                <th className={cn(headerPadding, "w-10")} aria-label="Expand" />
              )}
              
              {/* Selection checkbox column */}
              {selectable && (
                <th className={cn(headerPadding, "w-12")}>
                  <Checkbox
                    checked={allSelected}
                    indeterminate={someSelected}
                    onChange={handleSelectAll}
                    aria-label="Select all rows"
                  />
                </th>
              )}
              
              {columns.map((column) => {
                const isSortable = sortable && column.sortable !== false
                const isSorted = sortState.column === column.id
                
                return (
                  <th
                    key={column.id}
                    className={cn(
                      headerPadding,
                      "text-left text-xs font-semibold uppercase tracking-wider",
                      "text-gray-500 dark:text-gray-400",
                      bordered && "border-r border-gray-200 dark:border-dark-border/50 last:border-r-0",
                      column.hideOnMobile && "hidden md:table-cell",
                      column.align === "center" && "text-center",
                      column.align === "right" && "text-right",
                      isSortable && "cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200",
                      column.headerClassName
                    )}
                    style={{ 
                      width: column.width, 
                      minWidth: column.minWidth 
                    }}
                    onClick={() => isSortable && handleSort(column.id)}
                  >
                    <div className={cn(
                      "flex items-center gap-1",
                      column.align === "center" && "justify-center",
                      column.align === "right" && "justify-end"
                    )}>
                      <span>{column.header}</span>
                      
                      {isSortable && (
                        <span className="flex-shrink-0">
                          {isSorted ? (
                            sortState.direction === "asc" ? (
                              <ChevronUpIcon className="w-4 h-4 text-eliza-red" />
                            ) : (
                              <ChevronDownIcon className="w-4 h-4 text-eliza-red" />
                            )
                          ) : (
                            <ChevronUpDownIcon className="w-4 h-4 opacity-40" />
                          )}
                        </span>
                      )}
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
          
          {/* Body */}
          <tbody className="divide-y divide-gray-200 dark:divide-dark-border/50">
            {/* Loading State */}
            {loading && (
              Array.from({ length: loadingRows }).map((_, index) => (
                <tr key={`skeleton-${index}`}>
                  {expandable && (
                    <td className={cellPadding}>
                      <Skeleton variant="rectangular" width="16px" height="16px" />
                    </td>
                  )}
                  {selectable && (
                    <td className={cellPadding}>
                      <Skeleton variant="rectangular" width="18px" height="18px" />
                    </td>
                  )}
                  {columns.map((column) => (
                    <td 
                      key={column.id} 
                      className={cn(
                        cellPadding,
                        column.hideOnMobile && "hidden md:table-cell"
                      )}
                    >
                      <Skeleton variant="text" width="80%" />
                    </td>
                  ))}
                </tr>
              ))
            )}
            
            {/* Empty State */}
            {!loading && displayData.length === 0 && (
              <tr>
                <td 
                  colSpan={columns.length + (selectable ? 1 : 0) + (expandable ? 1 : 0)} 
                  className="px-4 py-12 text-center"
                >
                  {emptyContent || (
                    <div className="flex flex-col items-center justify-center text-gray-500 dark:text-gray-400">
                      {emptyIcon && (
                        <div className="mb-3 text-gray-400 dark:text-gray-500">
                          {emptyIcon}
                        </div>
                      )}
                      <p className="text-sm">{emptyMessage}</p>
                    </div>
                  )}
                </td>
              </tr>
            )}
            
            {/* Data Rows */}
            {!loading && displayData.map((row, rowIndex) => {
              const rowId = getRowId(row)
              const isSelected = selectedRows.has(rowId)
              const isExpanded = expandable && expandedRowIds.has(rowId)
              
              return (
                <React.Fragment key={rowId}>
                  <tr
                    className={cn(
                      "transition-colors",
                      hoverable && "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
                      striped && rowIndex % 2 === 1 && "bg-gray-50/50 dark:bg-dark-surface-2/50",
                      isSelected && "bg-eliza-red/5 dark:bg-eliza-red/10",
                      isExpanded && "bg-gray-50 dark:bg-dark-surface-2",
                      (onRowClick || expandable) && "cursor-pointer",
                      rowClassName?.(row)
                    )}
                    onClick={() => {
                      if (expandable) {
                        handleToggleExpand(rowId)
                      }
                      onRowClick?.(row)
                    }}
                  >
                    {/* Expand toggle */}
                    {expandable && (
                      <td 
                        className={cn(cellPadding, "w-10")}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleToggleExpand(rowId)
                        }}
                      >
                        <button
                          className={cn(
                            "p-0.5 rounded transition-transform duration-200",
                            "text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300",
                            isExpanded && "transform rotate-0",
                            !isExpanded && "transform -rotate-90"
                          )}
                          aria-label={isExpanded ? "Collapse row" : "Expand row"}
                          aria-expanded={isExpanded}
                        >
                          <ChevronDownIcon className="w-4 h-4" />
                        </button>
                      </td>
                    )}
                    
                    {/* Selection checkbox */}
                    {selectable && (
                      <td 
                        className={cellPadding}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Checkbox
                          checked={isSelected}
                          onChange={() => handleSelectRow(row)}
                          aria-label={`Select row ${rowId}`}
                        />
                      </td>
                    )}
                    
                    {columns.map((column) => (
                      <td
                        key={column.id}
                        className={cn(
                          cellPadding,
                          "text-sm text-charcoal dark:text-white",
                          bordered && "border-r border-gray-200 dark:border-dark-border/50 last:border-r-0",
                          column.hideOnMobile && "hidden md:table-cell",
                          column.align === "center" && "text-center",
                          column.align === "right" && "text-right",
                          column.cellClassName
                        )}
                      >
                        {renderCell(row, column)}
                      </td>
                    ))}
                  </tr>
                  
                  {/* Expanded Row Content */}
                  {isExpanded && renderExpandedRow && (
                    <tr className="bg-gray-50/50 dark:bg-dark-surface-2/50">
                      <td 
                        colSpan={columns.length + (selectable ? 1 : 0) + (expandable ? 1 : 0)}
                        className="px-4 py-4 border-t border-gray-100 dark:border-dark-border/30"
                      >
                        {renderExpandedRow(row)}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      
      {/* Pagination */}
      {paginated && totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 px-1">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {totalItems ? (
              <>
                Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, totalItems)} of {totalItems} results
              </>
            ) : (
              <>
                Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, data.length)} of {data.length} results
              </>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange?.(page - 1)}
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
              {/* Generate page numbers */}
              {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
                let pageNum: number
                
                if (totalPages <= 5) {
                  pageNum = i + 1
                } else if (page <= 3) {
                  pageNum = i + 1
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i
                } else {
                  pageNum = page - 2 + i
                }
                
                return (
                  <button
                    key={pageNum}
                    onClick={() => onPageChange?.(pageNum)}
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
                )
              })}
            </div>
            
            <button
              onClick={() => onPageChange?.(page + 1)}
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
  )
}

/* ===========================================
   Helper Components
   =========================================== */

/** Cell wrapper for consistent styling */
export function DataTableCell({ 
  children, 
  className 
}: { 
  children: React.ReactNode
  className?: string 
}) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {children}
    </div>
  )
}

/** Badge cell for status indicators */
export function DataTableBadge({ 
  children, 
  variant = "default" 
}: { 
  children: React.ReactNode
  variant?: "default" | "success" | "warning" | "error" | "info"
}) {
  const variantStyles = {
    default: "bg-gray-100 text-gray-700 dark:bg-dark-surface-2 dark:text-gray-300",
    success: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    warning: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    error: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    info: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  }
  
  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
      variantStyles[variant]
    )}>
      {children}
    </span>
  )
}

/** Avatar cell for user columns */
export function DataTableAvatar({ 
  src, 
  name, 
  subtitle 
}: { 
  src?: string
  name: string
  subtitle?: string
}) {
  const initials = name
    .split(" ")
    .map(n => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
  
  return (
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-dark-surface-2 flex items-center justify-center overflow-hidden flex-shrink-0">
        {src ? (
          <img src={src} alt={name} className="w-full h-full object-cover" />
        ) : (
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
            {initials}
          </span>
        )}
      </div>
      <div className="min-w-0">
        <div className="font-medium text-charcoal dark:text-white truncate">
          {name}
        </div>
        {subtitle && (
          <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
            {subtitle}
          </div>
        )}
      </div>
    </div>
  )
}

/** Action buttons cell */
export function DataTableActions({ 
  children 
}: { 
  children: React.ReactNode 
}) {
  return (
    <div className="flex items-center justify-end gap-1">
      {children}
    </div>
  )
}

/** Single action button */
export function DataTableActionButton({ 
  icon, 
  label, 
  onClick,
  variant = "default",
  disabled = false,
}: { 
  icon: React.ReactNode
  label: string
  onClick: () => void
  variant?: "default" | "danger"
  disabled?: boolean
}) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      disabled={disabled}
      className={cn(
        "p-1.5 rounded-lg transition-colors",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variant === "default" && "text-gray-500 hover:text-charcoal hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-dark-surface-2",
        variant === "danger" && "text-gray-500 hover:text-red-600 hover:bg-red-50 dark:text-gray-400 dark:hover:text-red-400 dark:hover:bg-red-900/20"
      )}
      title={label}
    >
      {icon}
    </button>
  )
}

export default DataTable
