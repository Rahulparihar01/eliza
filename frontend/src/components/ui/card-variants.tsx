/**
 * Card Variants - Extended Card Components
 * 
 * Different card styles for various use cases.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { ArrowUpIcon, ArrowDownIcon, ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   IMAGE CARD
   ============================================ */

interface ImageCardProps extends React.HTMLAttributes<HTMLDivElement> {
  image: string
  imageAlt?: string
  title: string
  description?: string
  badge?: string
  aspectRatio?: "video" | "square" | "wide"
  overlay?: boolean
}

const ImageCard = React.forwardRef<HTMLDivElement, ImageCardProps>(
  ({ className, image, imageAlt, title, description, badge, aspectRatio = "video", overlay, ...props }, ref) => {
    const aspectClasses = {
      video: "aspect-video",
      square: "aspect-square",
      wide: "aspect-[2/1]",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "group rounded-2xl border overflow-hidden bg-white",
          "border-gray-200 hover:border-gray-300 hover:shadow-lg",
          "dark:bg-dark-surface dark:border-dark-border/30 dark:hover:border-dark-border/50",
          "transition-all duration-200 cursor-pointer",
          className
        )}
        {...props}
      >
        <div className={cn("relative overflow-hidden", aspectClasses[aspectRatio])}>
          <img
            src={image}
            alt={imageAlt || title}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
          {overlay && (
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          )}
          {badge && (
            <span className="absolute top-3 left-3 px-2 py-1 text-xs font-medium rounded-full bg-white/90 text-charcoal dark:bg-dark-surface/90 dark:text-white">
              {badge}
            </span>
          )}
          {overlay && (
            <div className="absolute bottom-3 left-3 right-3">
              <h3 className="font-semibold text-white">{title}</h3>
              {description && (
                <p className="text-sm text-white/80 mt-1 line-clamp-2">{description}</p>
              )}
            </div>
          )}
        </div>
        {!overlay && (
          <div className="p-4">
            <h3 className="font-semibold text-charcoal dark:text-white">{title}</h3>
            {description && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{description}</p>
            )}
          </div>
        )}
      </div>
    )
  }
)
ImageCard.displayName = "ImageCard"

/* ============================================
   METRIC CARD (KPI)
   ============================================ */

interface MetricCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon?: React.ReactNode
  trend?: "up" | "down" | "neutral"
  variant?: "default" | "gradient" | "outlined"
}

const MetricCard = React.forwardRef<HTMLDivElement, MetricCardProps>(
  ({ className, title, value, change, changeLabel, icon, trend, variant = "default", ...props }, ref) => {
    const trendColor = trend === "up" 
      ? "text-green-600 dark:text-green-400" 
      : trend === "down" 
        ? "text-red-600 dark:text-red-400" 
        : "text-gray-500 dark:text-gray-400"

    const variantClasses = {
      default: "bg-white border-gray-200 dark:bg-dark-surface dark:border-dark-border/30",
      gradient: "bg-gradient-to-br from-eliza-red/10 to-eliza-red-coral/10 border-eliza-red/20 dark:from-eliza-red/20 dark:to-eliza-red-coral/20 dark:border-eliza-red/30",
      outlined: "bg-transparent border-2 border-gray-300 dark:border-dark-border",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "p-5 rounded-2xl border",
          variantClasses[variant],
          className
        )}
        {...props}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
            <p className="text-3xl font-bold text-charcoal dark:text-white mt-1">{value}</p>
            {change !== undefined && (
              <div className={cn("flex items-center gap-1 mt-2 text-sm", trendColor)}>
                {trend === "up" && <ArrowUpIcon className="w-4 h-4" />}
                {trend === "down" && <ArrowDownIcon className="w-4 h-4" />}
                <span className="font-medium">
                  {change > 0 ? "+" : ""}{change}%
                </span>
                {changeLabel && (
                  <span className="text-gray-500 dark:text-gray-400">{changeLabel}</span>
                )}
              </div>
            )}
          </div>
          {icon && (
            <div className="p-3 rounded-xl bg-gray-100 dark:bg-dark-surface-2">
              {icon}
            </div>
          )}
        </div>
      </div>
    )
  }
)
MetricCard.displayName = "MetricCard"

/* ============================================
   STAT CARD (Compact KPI)
   ============================================ */

interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
  value: string | number
  subValue?: string
  color?: "default" | "success" | "warning" | "danger" | "info"
}

const StatCard = React.forwardRef<HTMLDivElement, StatCardProps>(
  ({ className, label, value, subValue, color = "default", ...props }, ref) => {
    const colorClasses = {
      default: "border-l-gray-400",
      success: "border-l-green-500",
      warning: "border-l-amber-500",
      danger: "border-l-red-500",
      info: "border-l-blue-500",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "p-4 rounded-xl border-l-4 bg-white border border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/30",
          colorClasses[color],
          className
        )}
        {...props}
      >
        <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {label}
        </p>
        <p className="text-2xl font-bold text-charcoal dark:text-white mt-1">{value}</p>
        {subValue && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{subValue}</p>
        )}
      </div>
    )
  }
)
StatCard.displayName = "StatCard"

/* ============================================
   CONTENT CARD (Article/Blog style)
   ============================================ */

interface ContentCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  excerpt: string
  author?: {
    name: string
    avatar?: string
  }
  date?: string
  readTime?: string
  tags?: string[]
}

const ContentCard = React.forwardRef<HTMLDivElement, ContentCardProps>(
  ({ className, title, excerpt, author, date, readTime, tags, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "p-6 rounded-2xl border bg-white",
        "border-gray-200 hover:border-gray-300 hover:shadow-md",
        "dark:bg-dark-surface dark:border-dark-border/30 dark:hover:border-dark-border/50",
        "transition-all duration-200 cursor-pointer",
        className
      )}
      {...props}
    >
      {tags && tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 text-xs font-medium rounded-full bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20 dark:text-white"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      <h3 className="font-title text-xl font-medium text-charcoal dark:text-white leading-tight">
        {title}
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 line-clamp-3">
        {excerpt}
      </p>
      {(author || date || readTime) && (
        <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-100 dark:border-dark-border/30">
          {author && (
            <div className="flex items-center gap-2">
              {author.avatar ? (
                <img src={author.avatar} alt={author.name} className="w-6 h-6 rounded-full" />
              ) : (
                <div className="w-6 h-6 rounded-full bg-gray-200 dark:bg-dark-surface-2 flex items-center justify-center text-xs font-medium text-gray-600 dark:text-gray-400">
                  {author.name.charAt(0)}
                </div>
              )}
              <span className="text-sm font-medium text-charcoal dark:text-gray-200">{author.name}</span>
            </div>
          )}
          {(date || readTime) && (
            <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
              {date && <span>{date}</span>}
              {date && readTime && <span>•</span>}
              {readTime && <span>{readTime}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
)
ContentCard.displayName = "ContentCard"

/* ============================================
   LINK CARD (Navigation tile)
   ============================================ */

interface LinkCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  description?: string
  icon?: React.ReactNode
  href?: string
  external?: boolean
}

const LinkCard = React.forwardRef<HTMLDivElement, LinkCardProps>(
  ({ className, title, description, icon, href, external, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "group p-5 rounded-2xl border bg-white",
        "border-gray-200 hover:border-eliza-red/50 hover:shadow-md",
        "dark:bg-dark-surface dark:border-dark-border/30 dark:hover:border-eliza-red/50",
        "transition-all duration-200 cursor-pointer",
        className
      )}
      {...props}
    >
      <div className="flex items-start justify-between">
        {icon && (
          <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 dark:bg-dark-surface-2 dark:border-dark-border/30 text-gray-600 dark:text-gray-400 group-hover:text-eliza-red dark:group-hover:text-white group-hover:bg-eliza-red/10 dark:group-hover:bg-eliza-red/20 group-hover:border-eliza-red/20 dark:group-hover:border-eliza-red/30 transition-colors">
            {icon}
          </div>
        )}
        {external && (
          <ArrowTopRightOnSquareIcon className="w-4 h-4 text-gray-400 dark:text-gray-500 group-hover:text-eliza-red dark:group-hover:text-white transition-colors" />
        )}
      </div>
      <h3 className="font-semibold text-charcoal dark:text-white mt-4 group-hover:text-eliza-red dark:group-hover:text-white transition-colors">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {description}
        </p>
      )}
    </div>
  )
)
LinkCard.displayName = "LinkCard"

/* ============================================
   PROGRESS CARD (Adoption Dashboard)
   ============================================ */

interface ProgressCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  current: number
  target: number
  unit?: string
  icon?: React.ReactNode
  color?: "default" | "success" | "warning" | "danger"
}

const ProgressCard = React.forwardRef<HTMLDivElement, ProgressCardProps>(
  ({ className, title, current, target, unit = "", icon, color = "default", ...props }, ref) => {
    const percentage = Math.min(100, Math.round((current / target) * 100))
    
    const colorClasses = {
      default: "bg-eliza-red",
      success: "bg-green-500",
      warning: "bg-amber-500",
      danger: "bg-red-500",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "p-5 rounded-2xl border bg-white",
          "border-gray-200 dark:bg-dark-surface dark:border-dark-border/30",
          className
        )}
        {...props}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
            <p className="text-2xl font-bold text-charcoal dark:text-white mt-1">
              {current.toLocaleString()}{unit}
              <span className="text-sm font-normal text-gray-400 dark:text-gray-500 ml-1">
                / {target.toLocaleString()}{unit}
              </span>
            </p>
          </div>
          {icon && (
            <div className="p-2 rounded-lg bg-gray-100 dark:bg-dark-surface-2">
              {icon}
            </div>
          )}
        </div>
        <div className="w-full h-2 rounded-full bg-gray-100 dark:bg-dark-surface-2 overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all duration-500", colorClasses[color])}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          {percentage}% complete
        </p>
      </div>
    )
  }
)
ProgressCard.displayName = "ProgressCard"

export {
  ImageCard,
  MetricCard,
  StatCard,
  ContentCard,
  LinkCard,
  ProgressCard,
}
export type {
  ImageCardProps,
  MetricCardProps,
  StatCardProps,
  ContentCardProps,
  LinkCardProps,
  ProgressCardProps,
}
