/**
 * Tooltip - Hover Hint Component
 * 
 * Displays additional information on hover.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

interface TooltipProps {
  /** Tooltip content */
  content: React.ReactNode
  /** Element that triggers the tooltip */
  children: React.ReactElement
  /** Tooltip position */
  position?: "top" | "bottom" | "left" | "right"
  /** Delay before showing (ms) */
  delay?: number
  /** Additional class for tooltip */
  className?: string
}

const Tooltip: React.FC<TooltipProps> = ({
  content,
  children,
  position = "top",
  delay = 200,
  className,
}) => {
  const [visible, setVisible] = React.useState(false)
  const [coords, setCoords] = React.useState({ x: 0, y: 0 })
  const triggerRef = React.useRef<HTMLElement>(null)
  const tooltipRef = React.useRef<HTMLDivElement>(null)
  const timeoutRef = React.useRef<number>()

  const showTooltip = () => {
    timeoutRef.current = window.setTimeout(() => {
      setVisible(true)
    }, delay)
  }

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setVisible(false)
  }

  React.useEffect(() => {
    if (visible && triggerRef.current && tooltipRef.current) {
      const trigger = triggerRef.current.getBoundingClientRect()
      const tooltip = tooltipRef.current.getBoundingClientRect()

      let x = 0
      let y = 0

      switch (position) {
        case "top":
          x = trigger.left + trigger.width / 2 - tooltip.width / 2
          y = trigger.top - tooltip.height - 8
          break
        case "bottom":
          x = trigger.left + trigger.width / 2 - tooltip.width / 2
          y = trigger.bottom + 8
          break
        case "left":
          x = trigger.left - tooltip.width - 8
          y = trigger.top + trigger.height / 2 - tooltip.height / 2
          break
        case "right":
          x = trigger.right + 8
          y = trigger.top + trigger.height / 2 - tooltip.height / 2
          break
      }

      setCoords({ x, y })
    }
  }, [visible, position])

  React.useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  const child = React.cloneElement(children, {
    ref: triggerRef,
    onMouseEnter: (e: React.MouseEvent) => {
      showTooltip()
      children.props.onMouseEnter?.(e)
    },
    onMouseLeave: (e: React.MouseEvent) => {
      hideTooltip()
      children.props.onMouseLeave?.(e)
    },
    onFocus: (e: React.FocusEvent) => {
      showTooltip()
      children.props.onFocus?.(e)
    },
    onBlur: (e: React.FocusEvent) => {
      hideTooltip()
      children.props.onBlur?.(e)
    },
  })

  return (
    <>
      {child}
      {visible && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={cn(
            "fixed z-[100] px-3 py-1.5 text-sm rounded-lg shadow-lg",
            "bg-charcoal text-white",
            "dark:bg-gray-700 dark:text-gray-100",
            "transition-opacity duration-150",
            className
          )}
          style={{
            left: coords.x,
            top: coords.y,
          }}
        >
          {content}
        </div>
      )}
    </>
  )
}
Tooltip.displayName = "Tooltip"

export { Tooltip }
export type { TooltipProps }
