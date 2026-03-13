/**
 * DatePicker - Date Selection Component
 * 
 * Calendar-based date picker for forms and dashboards.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { 
  ChevronLeftIcon, 
  ChevronRightIcon,
  ChevronDownIcon,
  CalendarIcon,
} from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   HELPERS
   ============================================ */

const DAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
]

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay()
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getDate() === b.getDate() &&
    a.getMonth() === b.getMonth() &&
    a.getFullYear() === b.getFullYear()
}

/* ============================================
   CALENDAR
   ============================================ */

interface CalendarProps {
  selected?: Date | null
  onSelect?: (date: Date) => void
  minDate?: Date
  maxDate?: Date
  className?: string
}

const Calendar: React.FC<CalendarProps> = ({
  selected,
  onSelect,
  minDate,
  maxDate,
  className,
}) => {
  const today = new Date()
  const [viewDate, setViewDate] = React.useState(selected || today)
  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()

  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfMonth(year, month)
  
  const prevMonth = () => {
    setViewDate(new Date(year, month - 1, 1))
  }

  const nextMonth = () => {
    setViewDate(new Date(year, month + 1, 1))
  }

  const isDisabled = (date: Date): boolean => {
    if (minDate && date < minDate) return true
    if (maxDate && date > maxDate) return true
    return false
  }

  const days: (number | null)[] = []
  for (let i = 0; i < firstDay; i++) {
    days.push(null)
  }
  for (let i = 1; i <= daysInMonth; i++) {
    days.push(i)
  }

  return (
    <div className={cn("p-4 min-w-[280px]", className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button
          type="button"
          onClick={prevMonth}
          className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-surface-2 transition-colors"
        >
          <ChevronLeftIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </button>
        <span className="font-medium text-charcoal dark:text-white">
          {MONTHS[month]} {year}
        </span>
        <button
          type="button"
          onClick={nextMonth}
          className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-surface-2 transition-colors"
        >
          <ChevronRightIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </button>
      </div>

      {/* Days of week */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {DAYS.map((day) => (
          <div
            key={day}
            className="h-8 w-9 flex items-center justify-center text-xs font-medium text-gray-500 dark:text-gray-400"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {days.map((day, index) => {
          if (day === null) {
            return <div key={`empty-${index}`} className="h-9 w-9" />
          }

          const date = new Date(year, month, day)
          const isSelected = selected && isSameDay(date, selected)
          const isToday = isSameDay(date, today)
          const disabled = isDisabled(date)

          return (
            <button
              key={day}
              type="button"
              disabled={disabled}
              onClick={() => onSelect?.(date)}
              className={cn(
                "h-9 w-9 rounded-lg text-sm font-medium transition-colors",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red focus-visible:ring-offset-1",
                disabled && "opacity-50 cursor-not-allowed",
                isSelected
                  ? "bg-eliza-red text-white"
                  : isToday
                    ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20 dark:text-white"
                    : "text-charcoal dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-surface-2"
              )}
            >
              {day}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/* ============================================
   DATE PICKER
   ============================================ */

interface DatePickerProps {
  value?: Date | null
  onChange?: (date: Date | null) => void
  placeholder?: string
  minDate?: Date
  maxDate?: Date
  disabled?: boolean
  className?: string
}

const DatePicker: React.FC<DatePickerProps> = ({
  value,
  onChange,
  placeholder = "Select date",
  minDate,
  maxDate,
  disabled,
  className,
}) => {
  const [open, setOpen] = React.useState(false)
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Close on outside click
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleSelect = (date: Date) => {
    onChange?.(date)
    setOpen(false)
  }

  const hasValue = value !== null && value !== undefined

  return (
    <div ref={containerRef} className={cn("relative inline-block", className)}>
      <button
        type="button"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className={cn(
          // Base pill styles matching Chip component
          "inline-flex items-center gap-1.5 px-4 py-2 rounded-full",
          "text-xs font-medium transition-all duration-150",
          "cursor-pointer select-none border",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red focus-visible:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          // State-based styling (matching Chip pill variant)
          open && !hasValue
            // Active state (dropdown open, no value) - strong brand
            ? "border-eliza-red bg-eliza-red/10 text-eliza-red dark:border-eliza-red dark:bg-eliza-red/20 dark:text-white"
            : hasValue
              // Complete state (has date) - subtle brand
              ? "border-eliza-red/30 bg-eliza-red/5 text-eliza-red hover:border-eliza-red/40 hover:bg-eliza-red/10 dark:border-eliza-red/30 dark:bg-eliza-red/10 dark:text-white dark:hover:border-eliza-red/40 dark:hover:bg-eliza-red/15"
              // Default state - neutral
              : "border-gray-200 bg-white text-charcoal hover:border-gray-300 dark:border-dark-border/30 dark:bg-dark-surface dark:text-gray-300 dark:hover:border-dark-border/50"
        )}
      >
        <CalendarIcon className={cn(
          "w-3.5 h-3.5",
          hasValue || open
            ? "text-eliza-red dark:text-white" 
            : "text-gray-400 dark:text-gray-500"
        )} />
        <span className="truncate max-w-[120px]">
          {value ? formatDate(value) : placeholder}
        </span>
        <ChevronDownIcon className={cn(
          "w-3 h-3 transition-transform",
          open && "rotate-180"
        )} />
      </button>
      {open && (
        <div
          className={cn(
            "absolute z-50 mt-1 rounded-xl border shadow-lg",
            "bg-white border-gray-200",
            "dark:bg-dark-surface dark:border-dark-border/50"
          )}
        >
          <Calendar
            selected={value}
            onSelect={handleSelect}
            minDate={minDate}
            maxDate={maxDate}
          />
        </div>
      )}
    </div>
  )
}

/* ============================================
   DATE RANGE PICKER
   ============================================ */

interface DateRange {
  from: Date | null
  to: Date | null
}

interface DateRangePickerProps {
  value?: DateRange
  onChange?: (range: DateRange) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  presets?: { label: string; range: DateRange }[]
}

/* Range Calendar - shows range selection on single view */
interface RangeCalendarProps {
  value: DateRange
  onChange: (range: DateRange) => void
  minDate?: Date
  maxDate?: Date
  className?: string
}

const RangeCalendar: React.FC<RangeCalendarProps> = ({
  value,
  onChange,
  minDate,
  maxDate,
  className,
}) => {
  const today = new Date()
  const [viewDate, setViewDate] = React.useState(value.from || today)
  const [hoverDate, setHoverDate] = React.useState<Date | null>(null)
  const [selecting, setSelecting] = React.useState<"from" | "to">(
    value.from && !value.to ? "to" : "from"
  )
  
  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()

  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfMonth(year, month)
  
  const prevMonth = () => {
    setViewDate(new Date(year, month - 1, 1))
  }

  const nextMonth = () => {
    setViewDate(new Date(year, month + 1, 1))
  }

  const isDisabled = (date: Date): boolean => {
    if (minDate && date < minDate) return true
    if (maxDate && date > maxDate) return true
    return false
  }

  const isInRange = (date: Date): boolean => {
    if (!value.from) return false
    
    const endDate = selecting === "to" && hoverDate ? hoverDate : value.to
    if (!endDate) return false
    
    const start = value.from < endDate ? value.from : endDate
    const end = value.from < endDate ? endDate : value.from
    
    return date > start && date < end
  }

  const isRangeStart = (date: Date): boolean => {
    if (!value.from) return false
    return isSameDay(date, value.from)
  }

  const isRangeEnd = (date: Date): boolean => {
    if (selecting === "to" && hoverDate) {
      return isSameDay(date, hoverDate)
    }
    if (!value.to) return false
    return isSameDay(date, value.to)
  }

  const handleDateClick = (date: Date) => {
    if (selecting === "from") {
      onChange({ from: date, to: null })
      setSelecting("to")
    } else {
      // If clicking before the start date, swap them
      if (value.from && date < value.from) {
        onChange({ from: date, to: value.from })
      } else {
        onChange({ from: value.from, to: date })
      }
      setSelecting("from")
    }
  }

  const days: (number | null)[] = []
  for (let i = 0; i < firstDay; i++) {
    days.push(null)
  }
  for (let i = 1; i <= daysInMonth; i++) {
    days.push(i)
  }

  return (
    <div className={cn("p-4 min-w-[280px]", className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button
          type="button"
          onClick={prevMonth}
          className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-surface-2 transition-colors"
        >
          <ChevronLeftIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </button>
        <span className="font-medium text-charcoal dark:text-white">
          {MONTHS[month]} {year}
        </span>
        <button
          type="button"
          onClick={nextMonth}
          className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-surface-2 transition-colors"
        >
          <ChevronRightIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </button>
      </div>

      {/* Instruction */}
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2 text-center">
        {selecting === "from" ? "Select start date" : "Select end date"}
      </div>

      {/* Days of week */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {DAYS.map((day) => (
          <div
            key={day}
            className="h-8 w-9 flex items-center justify-center text-xs font-medium text-gray-500 dark:text-gray-400"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {days.map((day, index) => {
          if (day === null) {
            return <div key={`empty-${index}`} className="h-9 w-9" />
          }

          const date = new Date(year, month, day)
          const disabled = isDisabled(date)
          const isStart = isRangeStart(date)
          const isEnd = isRangeEnd(date)
          const inRange = isInRange(date)
          const isToday = isSameDay(date, today)

          return (
            <button
              key={day}
              type="button"
              disabled={disabled}
              onClick={() => handleDateClick(date)}
              onMouseEnter={() => selecting === "to" && setHoverDate(date)}
              onMouseLeave={() => setHoverDate(null)}
              className={cn(
                "h-9 w-9 rounded-lg text-sm font-medium transition-colors relative",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red focus-visible:ring-offset-1",
                disabled && "opacity-50 cursor-not-allowed",
                // Range start/end
                (isStart || isEnd) && "bg-eliza-red text-white z-10",
                // In range (between start and end)
                inRange && !isStart && !isEnd && "bg-eliza-red/15 text-charcoal dark:text-gray-100",
                // Today indicator
                isToday && !isStart && !isEnd && !inRange && "bg-gray-100 dark:bg-dark-surface-2 text-charcoal dark:text-gray-100",
                // Default state
                !isStart && !isEnd && !inRange && !isToday && "text-charcoal dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-surface-2"
              )}
            >
              {day}
            </button>
          )
        })}
      </div>
    </div>
  )
}

const DateRangePicker: React.FC<DateRangePickerProps> = ({
  value = { from: null, to: null },
  onChange,
  placeholder = "Select date range",
  disabled,
  className,
  presets,
}) => {
  const [open, setOpen] = React.useState(false)
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Close on outside click
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleRangeChange = (range: DateRange) => {
    onChange?.(range)
    // Close when both dates are selected
    if (range.from && range.to) {
      setOpen(false)
    }
  }

  const handlePreset = (range: DateRange) => {
    onChange?.(range)
    setOpen(false)
  }

  const displayValue = value.from && value.to
    ? `${formatDate(value.from)} - ${formatDate(value.to)}`
    : value.from
      ? `${formatDate(value.from)} - ...`
      : placeholder

  const hasValue = value.from !== null || value.to !== null
  const isComplete = value.from !== null && value.to !== null

  return (
    <div ref={containerRef} className={cn("relative inline-block", className)}>
      <button
        type="button"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className={cn(
          // Base pill styles matching Chip component
          "inline-flex items-center gap-1.5 px-4 py-2 rounded-full",
          "text-xs font-medium transition-all duration-150",
          "cursor-pointer select-none border",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red focus-visible:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          // State-based styling (matching Chip pill variant)
          open && !isComplete
            // Active state (dropdown open, no complete value) - strong brand
            ? "border-eliza-red bg-eliza-red/10 text-eliza-red dark:border-eliza-red dark:bg-eliza-red/20 dark:text-white"
            : hasValue
              // Has value (partial or complete) - subtle brand
              ? "border-eliza-red/30 bg-eliza-red/5 text-eliza-red hover:border-eliza-red/40 hover:bg-eliza-red/10 dark:border-eliza-red/30 dark:bg-eliza-red/10 dark:text-white dark:hover:border-eliza-red/40 dark:hover:bg-eliza-red/15"
              // Default state - neutral
              : "border-gray-200 bg-white text-charcoal hover:border-gray-300 dark:border-dark-border/30 dark:bg-dark-surface dark:text-gray-300 dark:hover:border-dark-border/50"
        )}
      >
        <CalendarIcon className={cn(
          "w-3.5 h-3.5",
          hasValue || open 
            ? "text-eliza-red dark:text-white" 
            : "text-gray-400 dark:text-gray-500"
        )} />
        <span className="truncate max-w-[160px]">
          {displayValue}
        </span>
        <ChevronDownIcon className={cn(
          "w-3 h-3 transition-transform",
          open && "rotate-180"
        )} />
      </button>
      {open && (
        <div
          className={cn(
            "absolute z-50 mt-1 rounded-xl border shadow-lg",
            "bg-white border-gray-200",
            "dark:bg-dark-surface dark:border-dark-border/50",
            "flex"
          )}
        >
          {presets && presets.length > 0 && (
            <div className="border-r border-gray-200 dark:border-dark-border/30 p-2 min-w-[140px]">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 px-2 py-1 uppercase tracking-wider">
                Presets
              </p>
              {presets.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => handlePreset(preset.range)}
                  className="w-full text-left px-2 py-1.5 text-sm rounded-lg hover:bg-gray-100 dark:hover:bg-dark-surface-2 text-charcoal dark:text-gray-200"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          )}
          <RangeCalendar
            value={value}
            onChange={handleRangeChange}
          />
        </div>
      )}
    </div>
  )
}

export { Calendar, DatePicker, DateRangePicker }
export type { CalendarProps, DatePickerProps, DateRangePickerProps, DateRange }
