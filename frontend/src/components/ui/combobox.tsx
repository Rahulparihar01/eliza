/**
 * Combobox / Autocomplete - Searchable Select Component
 * 
 * An input with dropdown suggestions for filtering and selection.
 */

import * as React from "react"
import { ChevronUpDownIcon, CheckIcon, XMarkIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   COMBOBOX CONTEXT
   ============================================ */

interface ComboboxOption {
  value: string
  label: string
  disabled?: boolean
  icon?: React.ReactNode
  description?: string
}

interface ComboboxContextValue {
  open: boolean
  setOpen: (open: boolean) => void
  search: string
  setSearch: (search: string) => void
  value: string | null
  onSelect: (value: string) => void
  highlightedIndex: number
  setHighlightedIndex: (index: number) => void
  filteredOptions: ComboboxOption[]
}

const ComboboxContext = React.createContext<ComboboxContextValue | undefined>(undefined)

const useCombobox = () => {
  const context = React.useContext(ComboboxContext)
  if (!context) {
    throw new Error("useCombobox must be used within a Combobox")
  }
  return context
}

/* ============================================
   COMBOBOX
   ============================================ */

interface ComboboxProps {
  /** Available options */
  options: ComboboxOption[]
  /** Selected value */
  value?: string | null
  /** Callback when value changes */
  onChange?: (value: string | null) => void
  /** Placeholder text */
  placeholder?: string
  /** Search placeholder */
  searchPlaceholder?: string
  /** Empty state message */
  emptyMessage?: string
  /** Allow clearing selection */
  clearable?: boolean
  /** Disabled state */
  disabled?: boolean
  /** Custom filter function */
  filterFn?: (option: ComboboxOption, search: string) => boolean
  /** Class name */
  className?: string
}

const Combobox = React.forwardRef<HTMLDivElement, ComboboxProps>(
  ({ 
    options, 
    value: controlledValue, 
    onChange, 
    placeholder = "Select...",
    searchPlaceholder = "Search...",
    emptyMessage = "No results found.",
    clearable = true,
    disabled = false,
    filterFn,
    className,
  }, ref) => {
    const [open, setOpen] = React.useState(false)
    const [search, setSearch] = React.useState("")
    const [internalValue, setInternalValue] = React.useState<string | null>(null)
    const [highlightedIndex, setHighlightedIndex] = React.useState(0)
    
    const inputRef = React.useRef<HTMLInputElement>(null)
    const listRef = React.useRef<HTMLDivElement>(null)

    const value = controlledValue !== undefined ? controlledValue : internalValue

    // Default filter function
    const defaultFilter = (option: ComboboxOption, searchTerm: string) => {
      const term = searchTerm.toLowerCase()
      return (
        option.label.toLowerCase().includes(term) ||
        option.value.toLowerCase().includes(term) ||
        (option.description?.toLowerCase().includes(term) ?? false)
      )
    }

    const filter = filterFn || defaultFilter

    // Filter options based on search
    const filteredOptions = React.useMemo(() => {
      if (!search) return options
      return options.filter(opt => filter(opt, search))
    }, [options, search, filter])

    // Reset highlighted index when filtered options change
    React.useEffect(() => {
      setHighlightedIndex(0)
    }, [filteredOptions])

    // Handle selection
    const handleSelect = (selectedValue: string) => {
      if (controlledValue === undefined) {
        setInternalValue(selectedValue)
      }
      onChange?.(selectedValue)
      setOpen(false)
      setSearch("")
    }

    // Handle clear
    const handleClear = (e: React.MouseEvent) => {
      e.stopPropagation()
      if (controlledValue === undefined) {
        setInternalValue(null)
      }
      onChange?.(null)
      setSearch("")
    }

    // Handle keyboard navigation
    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (!open) {
        if (e.key === "Enter" || e.key === "ArrowDown" || e.key === " ") {
          e.preventDefault()
          setOpen(true)
        }
        return
      }

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault()
          setHighlightedIndex(prev => 
            prev < filteredOptions.length - 1 ? prev + 1 : prev
          )
          break
        case "ArrowUp":
          e.preventDefault()
          setHighlightedIndex(prev => prev > 0 ? prev - 1 : prev)
          break
        case "Enter":
          e.preventDefault()
          if (filteredOptions[highlightedIndex] && !filteredOptions[highlightedIndex].disabled) {
            handleSelect(filteredOptions[highlightedIndex].value)
          }
          break
        case "Escape":
          e.preventDefault()
          setOpen(false)
          setSearch("")
          break
      }
    }

    // Close on click outside
    React.useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        const target = e.target as Node
        if (listRef.current && !listRef.current.contains(target)) {
          setOpen(false)
          setSearch("")
        }
      }

      if (open) {
        document.addEventListener("mousedown", handleClickOutside)
        return () => document.removeEventListener("mousedown", handleClickOutside)
      }
    }, [open])

    // Focus input when opening
    React.useEffect(() => {
      if (open && inputRef.current) {
        inputRef.current.focus()
      }
    }, [open])

    const selectedOption = options.find(opt => opt.value === value)

    return (
      <ComboboxContext.Provider value={{
        open,
        setOpen,
        search,
        setSearch,
        value,
        onSelect: handleSelect,
        highlightedIndex,
        setHighlightedIndex,
        filteredOptions,
      }}>
        <div ref={ref} className={cn("relative", className)}>
          {/* Trigger button */}
          <button
            type="button"
            onClick={() => !disabled && setOpen(!open)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            className={cn(
              "flex items-center justify-between w-full",
              "px-3 py-2 rounded-lg text-sm text-left",
              "border border-gray-200 dark:border-dark-border/50",
              "bg-white dark:bg-dark-surface",
              "hover:border-gray-300 dark:hover:border-dark-border",
              "focus:outline-none focus:ring-2 focus:ring-eliza-red/20 focus:border-eliza-red",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "transition-colors"
            )}
          >
            <span className={cn(
              "truncate",
              selectedOption ? "text-charcoal dark:text-white" : "text-gray-400 dark:text-gray-500"
            )}>
              {selectedOption ? (
                <span className="flex items-center gap-2">
                  {selectedOption.icon}
                  {selectedOption.label}
                </span>
              ) : placeholder}
            </span>
            <div className="flex items-center gap-1 ml-2">
              {clearable && selectedOption && (
                <span
                  onClick={handleClear}
                  className="p-0.5 rounded hover:bg-gray-100 dark:hover:bg-dark-surface-2 cursor-pointer"
                >
                  <XMarkIcon className="w-4 h-4 text-gray-400" />
                </span>
              )}
              <ChevronUpDownIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
            </div>
          </button>

          {/* Dropdown */}
          {open && (
            <div
              ref={listRef}
              className={cn(
                "absolute z-50 w-full mt-1",
                "bg-white dark:bg-dark-surface",
                "border border-gray-200 dark:border-dark-border/50",
                "rounded-lg shadow-lg",
                "overflow-hidden"
              )}
            >
              {/* Search input */}
              <div className="p-2 border-b border-gray-100 dark:border-dark-border/30">
                <div className="relative">
                  <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    ref={inputRef}
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={searchPlaceholder}
                    className={cn(
                      "w-full pl-8 pr-3 py-1.5 text-sm",
                      "bg-gray-50 dark:bg-dark-surface-2",
                      "border border-gray-200 dark:border-dark-border/50",
                      "rounded-md",
                      "focus:outline-none focus:ring-1 focus:ring-eliza-red/20 focus:border-eliza-red",
                      "placeholder:text-gray-400 dark:placeholder:text-gray-500",
                      "text-charcoal dark:text-white"
                    )}
                  />
                </div>
              </div>

              {/* Options list */}
              <div className="max-h-60 overflow-y-auto py-1">
                {filteredOptions.length === 0 ? (
                  <div className="px-3 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                    {emptyMessage}
                  </div>
                ) : (
                  filteredOptions.map((option, index) => (
                    <ComboboxOption
                      key={option.value}
                      option={option}
                      index={index}
                    />
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </ComboboxContext.Provider>
    )
  }
)
Combobox.displayName = "Combobox"

/* ============================================
   COMBOBOX OPTION
   ============================================ */

interface ComboboxOptionProps {
  option: ComboboxOption
  index: number
}

const ComboboxOption: React.FC<ComboboxOptionProps> = ({ option, index }) => {
  const { value, onSelect, highlightedIndex, setHighlightedIndex } = useCombobox()
  const isSelected = value === option.value
  const isHighlighted = highlightedIndex === index

  return (
    <button
      type="button"
      onClick={() => !option.disabled && onSelect(option.value)}
      onMouseEnter={() => setHighlightedIndex(index)}
      disabled={option.disabled}
      className={cn(
        "flex items-center justify-between w-full px-3 py-2 text-sm text-left",
        "transition-colors",
        isHighlighted && "bg-gray-50 dark:bg-dark-surface-2",
        isSelected && "bg-eliza-red/10 dark:bg-eliza-red/20",
        option.disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        {option.icon && (
          <span className="flex-shrink-0 text-gray-500 dark:text-gray-400">
            {option.icon}
          </span>
        )}
        <div className="min-w-0">
          <div className={cn(
            "truncate",
            isSelected ? "text-eliza-red dark:text-white font-medium" : "text-charcoal dark:text-gray-200"
          )}>
            {option.label}
          </div>
          {option.description && (
            <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
              {option.description}
            </div>
          )}
        </div>
      </div>
      {isSelected && (
        <CheckIcon className="w-4 h-4 text-eliza-red dark:text-white flex-shrink-0" />
      )}
    </button>
  )
}

/* ============================================
   MULTI COMBOBOX (for selecting multiple)
   ============================================ */

interface MultiComboboxProps {
  /** Available options */
  options: ComboboxOption[]
  /** Selected values */
  value?: string[]
  /** Callback when values change */
  onChange?: (values: string[]) => void
  /** Placeholder text */
  placeholder?: string
  /** Search placeholder */
  searchPlaceholder?: string
  /** Empty state message */
  emptyMessage?: string
  /** Max items to show before collapsing */
  maxDisplayed?: number
  /** Disabled state */
  disabled?: boolean
  /** Class name */
  className?: string
}

const MultiCombobox = React.forwardRef<HTMLDivElement, MultiComboboxProps>(
  ({ 
    options, 
    value: controlledValue = [], 
    onChange, 
    placeholder = "Select items...",
    searchPlaceholder = "Search...",
    emptyMessage = "No results found.",
    maxDisplayed = 3,
    disabled = false,
    className,
  }, ref) => {
    const [open, setOpen] = React.useState(false)
    const [search, setSearch] = React.useState("")
    const [highlightedIndex, setHighlightedIndex] = React.useState(0)
    
    const inputRef = React.useRef<HTMLInputElement>(null)
    const containerRef = React.useRef<HTMLDivElement>(null)

    // Filter options
    const filteredOptions = React.useMemo(() => {
      if (!search) return options
      const term = search.toLowerCase()
      return options.filter(opt => 
        opt.label.toLowerCase().includes(term) ||
        opt.value.toLowerCase().includes(term)
      )
    }, [options, search])

    // Reset highlighted index
    React.useEffect(() => {
      setHighlightedIndex(0)
    }, [filteredOptions])

    // Toggle selection
    const toggleSelection = (optionValue: string) => {
      const newValues = controlledValue.includes(optionValue)
        ? controlledValue.filter(v => v !== optionValue)
        : [...controlledValue, optionValue]
      onChange?.(newValues)
    }

    // Remove item
    const removeItem = (optionValue: string, e: React.MouseEvent) => {
      e.stopPropagation()
      onChange?.(controlledValue.filter(v => v !== optionValue))
    }

    // Keyboard navigation
    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (!open) {
        if (e.key === "Enter" || e.key === "ArrowDown" || e.key === " ") {
          e.preventDefault()
          setOpen(true)
        }
        return
      }

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault()
          setHighlightedIndex(prev => 
            prev < filteredOptions.length - 1 ? prev + 1 : prev
          )
          break
        case "ArrowUp":
          e.preventDefault()
          setHighlightedIndex(prev => prev > 0 ? prev - 1 : prev)
          break
        case "Enter":
          e.preventDefault()
          if (filteredOptions[highlightedIndex] && !filteredOptions[highlightedIndex].disabled) {
            toggleSelection(filteredOptions[highlightedIndex].value)
          }
          break
        case "Escape":
          e.preventDefault()
          setOpen(false)
          setSearch("")
          break
        case "Backspace":
          if (!search && controlledValue.length > 0) {
            onChange?.(controlledValue.slice(0, -1))
          }
          break
      }
    }

    // Close on outside click
    React.useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
          setOpen(false)
          setSearch("")
        }
      }

      if (open) {
        document.addEventListener("mousedown", handleClickOutside)
        return () => document.removeEventListener("mousedown", handleClickOutside)
      }
    }, [open])

    const selectedOptions = options.filter(opt => controlledValue.includes(opt.value))
    const displayedOptions = selectedOptions.slice(0, maxDisplayed)
    const remainingCount = selectedOptions.length - maxDisplayed

    return (
      <div ref={ref} className={cn("relative", className)}>
        {/* Trigger */}
        <div
          ref={containerRef}
          onClick={() => !disabled && setOpen(true)}
          className={cn(
            "flex flex-wrap items-center gap-1.5 min-h-[42px]",
            "px-2 py-1.5 rounded-lg text-sm",
            "border border-gray-200 dark:border-dark-border/50",
            "bg-white dark:bg-dark-surface",
            "hover:border-gray-300 dark:hover:border-dark-border",
            open && "ring-2 ring-eliza-red/20 border-eliza-red",
            disabled && "opacity-50 cursor-not-allowed",
            "transition-colors cursor-text"
          )}
        >
          {/* Selected items as chips */}
          {displayedOptions.map(opt => (
            <span
              key={opt.value}
              className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium",
                "bg-gray-100 dark:bg-dark-surface-2",
                "text-charcoal dark:text-gray-200"
              )}
            >
              {opt.label}
              <XMarkIcon
                className="w-3 h-3 cursor-pointer hover:text-eliza-red"
                onClick={(e) => removeItem(opt.value, e)}
              />
            </span>
          ))}
          
          {remainingCount > 0 && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              +{remainingCount} more
            </span>
          )}

          {/* Input */}
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setOpen(true)}
            placeholder={controlledValue.length === 0 ? placeholder : ""}
            disabled={disabled}
            className={cn(
              "flex-1 min-w-[80px] py-1 bg-transparent",
              "focus:outline-none focus:ring-0 border-none",
              "placeholder:text-gray-400 dark:placeholder:text-gray-500",
              "text-charcoal dark:text-white"
            )}
          />
        </div>

        {/* Dropdown */}
        {open && (
          <div className={cn(
            "absolute z-50 w-full mt-1",
            "bg-white dark:bg-dark-surface",
            "border border-gray-200 dark:border-dark-border/50",
            "rounded-lg shadow-lg",
            "max-h-60 overflow-y-auto py-1"
          )}>
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                {emptyMessage}
              </div>
            ) : (
              filteredOptions.map((option, index) => {
                const isSelected = controlledValue.includes(option.value)
                const isHighlighted = highlightedIndex === index

                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => !option.disabled && toggleSelection(option.value)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    disabled={option.disabled}
                    className={cn(
                      "flex items-center justify-between w-full px-3 py-2 text-sm text-left",
                      "transition-colors",
                      isHighlighted && "bg-gray-50 dark:bg-dark-surface-2",
                      option.disabled && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        "w-4 h-4 rounded border flex items-center justify-center",
                        isSelected
                          ? "bg-eliza-red border-eliza-red"
                          : "border-gray-300 dark:border-gray-600"
                      )}>
                        {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                      </div>
                      <span className="text-charcoal dark:text-gray-200">
                        {option.label}
                      </span>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        )}
      </div>
    )
  }
)
MultiCombobox.displayName = "MultiCombobox"

/* ============================================
   EXPORTS
   ============================================ */

export { Combobox, MultiCombobox }
export type { ComboboxProps, ComboboxOption, MultiComboboxProps }
