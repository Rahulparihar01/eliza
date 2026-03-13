/**
 * Slider Input
 * 
 * A combined slider and number input component for selecting numeric values.
 * Values sync bidirectionally between the slider and input.
 * 
 * Usage:
 * ```tsx
 * <SliderInput
 *   label="Market Search Limit"
 *   description="Max candidates to search from external talent market"
 *   value={50}
 *   onChange={setValue}
 *   min={0}
 *   max={200}
 * />
 * ```
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"
import { Label } from "./label"

interface SliderInputProps {
  /** Label text displayed above the slider */
  label: string
  /** Current value */
  value: number
  /** Callback when value changes */
  onChange: (value: number) => void
  /** Minimum value (default: 0) */
  min?: number
  /** Maximum value (default: 100) */
  max?: number
  /** Step increment (default: 1) */
  step?: number
  /** Optional description text below the label */
  description?: string
  /** Whether the input is disabled */
  disabled?: boolean
  /** Additional className for the container */
  className?: string
}

const SliderInput = React.forwardRef<HTMLDivElement, SliderInputProps>(
  (
    {
      label,
      value,
      onChange,
      min = 0,
      max = 100,
      step = 1,
      description,
      disabled = false,
      className,
    },
    ref
  ) => {
    const [localValue, setLocalValue] = React.useState<string>(String(value))

    // Sync local value when prop value changes
    React.useEffect(() => {
      setLocalValue(String(value))
    }, [value])

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = Number(e.target.value)
      setLocalValue(String(newValue))
      onChange(newValue)
    }

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const inputValue = e.target.value
      setLocalValue(inputValue)

      // Only update parent if it's a valid number within range
      const numValue = Number(inputValue)
      if (!isNaN(numValue) && inputValue !== '') {
        const clampedValue = Math.min(max, Math.max(min, numValue))
        onChange(clampedValue)
      }
    }

    const handleInputBlur = () => {
      // On blur, ensure value is valid and clamped
      const numValue = Number(localValue)
      if (isNaN(numValue) || localValue === '') {
        setLocalValue(String(value))
      } else {
        const clampedValue = Math.min(max, Math.max(min, numValue))
        setLocalValue(String(clampedValue))
        onChange(clampedValue)
      }
    }

    // Calculate percentage for gradient fill
    const percentage = ((value - min) / (max - min)) * 100

    // Detect dark mode for inline style
    const [isDark, setIsDark] = React.useState(false)
    React.useEffect(() => {
      const checkDarkMode = () => {
        setIsDark(document.documentElement.classList.contains('dark'))
      }
      checkDarkMode()
      // Watch for class changes
      const observer = new MutationObserver(checkDarkMode)
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
      return () => observer.disconnect()
    }, [])

    // Colors for the slider track fill
    const fillColor = isDark ? '#E5E7EB' : '#2D3748' // gray-200 in dark, charcoal in light
    const trackColor = isDark ? '#374151' : '#E5E7EB' // gray-700 in dark, gray-200 in light

    return (
      <div ref={ref} className={cn("space-y-2", className)}>
        {/* Label and description */}
        <div>
          <Label className="text-sm font-medium text-charcoal dark:text-gray-100">
            {label}
          </Label>
          {description && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {description}
            </p>
          )}
        </div>

        {/* Slider and input row */}
        <div className="flex items-center gap-4">
          {/* Slider */}
          <div className="flex-1 relative">
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={value}
              onChange={handleSliderChange}
              disabled={disabled}
              className={cn(
                "w-full h-2 rounded-full appearance-none cursor-pointer",
                "bg-gray-200 dark:bg-dark-border",
                // Webkit (Chrome, Safari, Edge)
                "[&::-webkit-slider-thumb]:appearance-none",
                "[&::-webkit-slider-thumb]:w-4",
                "[&::-webkit-slider-thumb]:h-4",
                "[&::-webkit-slider-thumb]:rounded-full",
                "[&::-webkit-slider-thumb]:bg-charcoal",
                "[&::-webkit-slider-thumb]:dark:bg-gray-100",
                "[&::-webkit-slider-thumb]:cursor-pointer",
                "[&::-webkit-slider-thumb]:shadow-md",
                "[&::-webkit-slider-thumb]:transition-transform",
                "[&::-webkit-slider-thumb]:hover:scale-110",
                "[&::-webkit-slider-thumb]:border-2",
                "[&::-webkit-slider-thumb]:border-white",
                "[&::-webkit-slider-thumb]:dark:border-dark-surface",
                // Firefox
                "[&::-moz-range-thumb]:w-4",
                "[&::-moz-range-thumb]:h-4",
                "[&::-moz-range-thumb]:rounded-full",
                "[&::-moz-range-thumb]:bg-charcoal",
                "[&::-moz-range-thumb]:dark:bg-gray-100",
                "[&::-moz-range-thumb]:border-2",
                "[&::-moz-range-thumb]:border-white",
                "[&::-moz-range-thumb]:dark:border-dark-surface",
                "[&::-moz-range-thumb]:cursor-pointer",
                "[&::-moz-range-thumb]:shadow-md",
                // Track styling
                "[&::-webkit-slider-runnable-track]:rounded-full",
                "[&::-moz-range-track]:rounded-full",
                // Disabled state
                disabled && "opacity-50 cursor-not-allowed",
                disabled && "[&::-webkit-slider-thumb]:cursor-not-allowed",
                disabled && "[&::-moz-range-thumb]:cursor-not-allowed"
              )}
              style={{
                background: `linear-gradient(to right, ${fillColor} 0%, ${fillColor} ${percentage}%, transparent ${percentage}%, transparent 100%), linear-gradient(to right, ${trackColor} 0%, ${trackColor} 100%)`,
              }}
            />
          </div>

          {/* Number input */}
          <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={localValue}
            onChange={handleInputChange}
            onBlur={handleInputBlur}
            disabled={disabled}
            className={cn(
              "w-20 px-3 py-1.5 text-sm text-center rounded-lg",
              "bg-white dark:bg-dark-surface",
              "border border-gray-200 dark:border-dark-border",
              "text-charcoal dark:text-gray-100",
              "focus:outline-none focus:ring-2 focus:ring-charcoal/20 focus:border-charcoal dark:focus:ring-gray-400/20 dark:focus:border-gray-400",
              "transition-colors",
              // Hide spinner buttons
              "[appearance:textfield]",
              "[&::-webkit-outer-spin-button]:appearance-none",
              "[&::-webkit-inner-spin-button]:appearance-none",
              disabled && "opacity-50 cursor-not-allowed"
            )}
          />
        </div>

        {/* Min/max labels */}
        <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      </div>
    )
  }
)
SliderInput.displayName = "SliderInput"

export { SliderInput }
export type { SliderInputProps }
