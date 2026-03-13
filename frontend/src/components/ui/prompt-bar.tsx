/**
 * PromptBar - AI Input Component Variants
 * 
 * Different prompt bar configurations for various use cases.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import {
  ArrowUpIcon,
  PaperClipIcon,
  MicrophoneIcon,
  PhotoIcon,
  Cog6ToothIcon,
  StopIcon,
  XMarkIcon,
  DocumentIcon,
  ChevronDownIcon,
  CheckIcon,
  CircleStackIcon,
} from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   BASIC PROMPT BAR
   ============================================ */

interface PromptBarProps {
  value?: string
  onChange?: (value: string) => void
  onSubmit?: (value: string) => void
  placeholder?: string
  disabled?: boolean
  loading?: boolean
  className?: string
}

const PromptBar = React.forwardRef<HTMLTextAreaElement, PromptBarProps>(
  ({ value, onChange, onSubmit, placeholder = "Ask anything...", disabled, loading, className }, ref) => {
    const [internalValue, setInternalValue] = React.useState("")
    const textareaRef = React.useRef<HTMLTextAreaElement>(null)

    const currentValue = value ?? internalValue

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value
      if (value === undefined) {
        setInternalValue(newValue)
      }
      onChange?.(newValue)
    }

    const handleSubmit = () => {
      if (currentValue.trim() && !disabled && !loading) {
        onSubmit?.(currentValue)
        if (value === undefined) {
          setInternalValue("")
        }
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    }

    return (
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-xl border",
          "bg-white border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/50",
          "focus-within:ring-2 focus-within:ring-eliza-red focus-within:border-transparent",
          className
        )}
      >
        <textarea
          ref={ref || textareaRef}
          value={currentValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent border-none outline-none focus:ring-0",
            "text-charcoal dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500",
            "text-sm min-h-[24px] max-h-[120px]",
            "[&:focus]:outline-none [&:focus]:ring-0 [&:focus]:border-none"
          )}
          style={{ height: "auto" }}
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={disabled || loading || !currentValue.trim()}
          className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0",
            "bg-eliza-red text-white hover:bg-eliza-red-light",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          {loading ? (
            <StopIcon className="w-4 h-4" />
          ) : (
            <ArrowUpIcon className="w-4 h-4" />
          )}
        </button>
      </div>
    )
  }
)
PromptBar.displayName = "PromptBar"

/* ============================================
   PROMPT BAR WITH ATTACHMENTS
   ============================================ */

interface Attachment {
  id: string
  name: string
  type: "file" | "image"
  size?: number
  preview?: string // For image previews
}

interface PromptBarWithAttachmentsProps extends PromptBarProps {
  attachments?: Attachment[]
  onAttachmentsChange?: (attachments: Attachment[]) => void
  maxAttachments?: number
  acceptedFileTypes?: string
}

const PromptBarWithAttachments = React.forwardRef<HTMLTextAreaElement, PromptBarWithAttachmentsProps>(
  ({
    value,
    onChange,
    onSubmit,
    placeholder = "Ask anything or attach files...",
    disabled,
    loading,
    attachments = [],
    onAttachmentsChange,
    maxAttachments = 5,
    acceptedFileTypes = "*",
    className,
  }, ref) => {
    const [internalValue, setInternalValue] = React.useState("")
    const [isDragging, setIsDragging] = React.useState(false)
    const fileInputRef = React.useRef<HTMLInputElement>(null)
    const dropRef = React.useRef<HTMLDivElement>(null)

    const currentValue = value ?? internalValue

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value
      if (value === undefined) {
        setInternalValue(newValue)
      }
      onChange?.(newValue)
    }

    const handleSubmit = () => {
      if ((currentValue.trim() || attachments.length > 0) && !disabled && !loading) {
        onSubmit?.(currentValue)
        if (value === undefined) {
          setInternalValue("")
        }
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    }

    const processFiles = (files: FileList | null) => {
      if (!files) return

      const newAttachments: Attachment[] = Array.from(files)
        .slice(0, maxAttachments - attachments.length)
        .map((file) => {
          const isImage = file.type.startsWith("image/")
          const attachment: Attachment = {
            id: Math.random().toString(36).substring(2, 9),
            name: file.name,
            type: isImage ? "image" : "file",
            size: file.size,
          }

          // Create preview for images
          if (isImage) {
            const reader = new FileReader()
            reader.onload = (e) => {
              const preview = e.target?.result as string
              onAttachmentsChange?.(
                [...attachments, ...newAttachments].map((a) =>
                  a.id === attachment.id ? { ...a, preview } : a
                )
              )
            }
            reader.readAsDataURL(file)
          }

          return attachment
        })

      onAttachmentsChange?.([...attachments, ...newAttachments])
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      processFiles(e.target.files)
      e.target.value = ""
    }

    const handleDragEnter = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer.types.includes('Files')) {
        setIsDragging(true)
      }
    }

    const handleDragLeave = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      // Only set to false if we're leaving the container entirely
      const rect = dropRef.current?.getBoundingClientRect()
      if (rect) {
        const { clientX, clientY } = e
        if (
          clientX <= rect.left ||
          clientX >= rect.right ||
          clientY <= rect.top ||
          clientY >= rect.bottom
        ) {
          setIsDragging(false)
        }
      }
    }

    const handleDragOver = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer.types.includes('Files')) {
        setIsDragging(true)
      }
    }

    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)
      processFiles(e.dataTransfer.files)
    }

    const removeAttachment = (id: string) => {
      onAttachmentsChange?.(attachments.filter((a) => a.id !== id))
    }

    const formatFileSize = (bytes: number): string => {
      if (bytes < 1024) return `${bytes} B`
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    return (
      <div
        ref={dropRef}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={cn(
          "rounded-xl border transition-colors",
          "bg-white border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/50",
          "focus-within:ring-2 focus-within:ring-eliza-red focus-within:border-transparent",
          isDragging && "ring-2 ring-eliza-red border-eliza-red bg-eliza-red/10 dark:bg-eliza-red/15",
          className
        )}
      >
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 px-3 pt-2">
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className={cn(
                  "relative group",
                  attachment.type === "image" && attachment.preview
                    ? "w-16 h-16"
                    : "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm bg-gray-100 dark:bg-dark-surface-2 text-charcoal dark:text-gray-200"
                )}
              >
                {attachment.type === "image" && attachment.preview ? (
                  <>
                    <img
                      src={attachment.preview}
                      alt={attachment.name}
                      className="w-full h-full object-cover rounded-lg"
                    />
                    <button
                      type="button"
                      onClick={() => removeAttachment(attachment.id)}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-800 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <XMarkIcon className="w-3 h-3" />
                    </button>
                  </>
                ) : (
                  <>
                    <DocumentIcon className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="max-w-[120px] truncate text-xs">{attachment.name}</span>
                    {attachment.size && (
                      <span className="text-[10px] text-gray-400">
                        {formatFileSize(attachment.size)}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeAttachment(attachment.id)}
                      className="p-0.5 hover:bg-gray-200 dark:hover:bg-dark-border rounded"
                    >
                      <XMarkIcon className="w-3 h-3 text-gray-500" />
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="flex items-center gap-2 px-3 py-2">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={acceptedFileTypes}
            onChange={handleFileSelect}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || attachments.length >= maxAttachments}
            className={cn(
              "p-1.5 rounded-lg transition-colors flex-shrink-0",
              "text-gray-400 hover:bg-gray-100 hover:text-gray-600",
              "dark:text-gray-500 dark:hover:bg-dark-surface-2 dark:hover:text-gray-300",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            <PaperClipIcon className="w-5 h-5" />
          </button>
          <textarea
            ref={ref}
            value={currentValue}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className={cn(
              "flex-1 resize-none bg-transparent border-none outline-none focus:ring-0",
              "text-charcoal dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500",
              "text-sm min-h-[24px] max-h-[120px]",
              "[&:focus]:outline-none [&:focus]:ring-0 [&:focus]:border-none"
            )}
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={disabled || loading || (!currentValue.trim() && attachments.length === 0)}
            className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0",
              "bg-eliza-red text-white hover:bg-eliza-red-light",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {loading ? (
              <StopIcon className="w-4 h-4" />
            ) : (
              <ArrowUpIcon className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Drag overlay hint */}
        {isDragging && (
          <div className="absolute inset-0 flex items-center justify-center bg-eliza-red/10 dark:bg-eliza-red/20 rounded-xl pointer-events-none border-2 border-dashed border-eliza-red">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white dark:bg-dark-surface shadow-lg">
              <PaperClipIcon className="w-5 h-5 text-eliza-red" />
              <p className="text-sm font-medium text-eliza-red dark:text-white">Drop files here</p>
            </div>
          </div>
        )}
      </div>
    )
  }
)
PromptBarWithAttachments.displayName = "PromptBarWithAttachments"

/* ============================================
   PROMPT BAR WITH TOOLS (Full featured)
   ============================================ */

interface Tool {
  id: string
  name: string
  icon: React.ReactNode
  description?: string
}

interface PromptBarWithToolsProps extends PromptBarProps {
  tools?: Tool[]
  selectedTools?: string[]
  onToolsChange?: (toolIds: string[]) => void
  attachments?: Attachment[]
  onAttachmentsChange?: (attachments: Attachment[]) => void
  maxAttachments?: number
  showVoice?: boolean
  onVoiceClick?: () => void
}

const PromptBarWithTools = React.forwardRef<HTMLTextAreaElement, PromptBarWithToolsProps>(
  ({
    value,
    onChange,
    onSubmit,
    placeholder = "Ask anything...",
    disabled,
    loading,
    tools = [],
    selectedTools = [],
    onToolsChange,
    attachments = [],
    onAttachmentsChange,
    maxAttachments = 5,
    showVoice,
    onVoiceClick,
    className,
  }, ref) => {
    const [internalValue, setInternalValue] = React.useState("")
    const [showToolsMenu, setShowToolsMenu] = React.useState(false)
    const [isDragging, setIsDragging] = React.useState(false)
    const toolsRef = React.useRef<HTMLDivElement>(null)
    const fileInputRef = React.useRef<HTMLInputElement>(null)
    const dropRef = React.useRef<HTMLDivElement>(null)

    const currentValue = value ?? internalValue

    // Close tools menu on outside click
    React.useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (toolsRef.current && !toolsRef.current.contains(e.target as Node)) {
          setShowToolsMenu(false)
        }
      }
      document.addEventListener("mousedown", handleClickOutside)
      return () => document.removeEventListener("mousedown", handleClickOutside)
    }, [])

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value
      if (value === undefined) {
        setInternalValue(newValue)
      }
      onChange?.(newValue)
    }

    const handleSubmit = () => {
      if ((currentValue.trim() || attachments.length > 0) && !disabled && !loading) {
        onSubmit?.(currentValue)
        if (value === undefined) {
          setInternalValue("")
        }
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    }

    const toggleTool = (toolId: string) => {
      if (selectedTools.includes(toolId)) {
        onToolsChange?.(selectedTools.filter((id) => id !== toolId))
      } else {
        onToolsChange?.([...selectedTools, toolId])
      }
    }

    const processFiles = (files: FileList | null) => {
      if (!files) return

      const newAttachments: Attachment[] = Array.from(files)
        .slice(0, maxAttachments - attachments.length)
        .map((file) => {
          const isImage = file.type.startsWith("image/")
          const attachment: Attachment = {
            id: Math.random().toString(36).substring(2, 9),
            name: file.name,
            type: isImage ? "image" : "file",
            size: file.size,
          }

          // Create preview for images
          if (isImage) {
            const reader = new FileReader()
            reader.onload = (e) => {
              const preview = e.target?.result as string
              onAttachmentsChange?.(
                [...attachments, ...newAttachments].map((a) =>
                  a.id === attachment.id ? { ...a, preview } : a
                )
              )
            }
            reader.readAsDataURL(file)
          }

          return attachment
        })

      onAttachmentsChange?.([...attachments, ...newAttachments])
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      processFiles(e.target.files)
      e.target.value = ""
    }

    const handleDragEnter = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer.types.includes('Files')) {
        setIsDragging(true)
      }
    }

    const handleDragLeave = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      // Only set to false if we're leaving the container entirely
      const rect = dropRef.current?.getBoundingClientRect()
      if (rect) {
        const { clientX, clientY } = e
        if (
          clientX <= rect.left ||
          clientX >= rect.right ||
          clientY <= rect.top ||
          clientY >= rect.bottom
        ) {
          setIsDragging(false)
        }
      }
    }

    const handleDragOver = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer.types.includes('Files')) {
        setIsDragging(true)
      }
    }

    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)
      processFiles(e.dataTransfer.files)
    }

    const removeAttachment = (id: string) => {
      onAttachmentsChange?.(attachments.filter((a) => a.id !== id))
    }

    const formatFileSize = (bytes: number): string => {
      if (bytes < 1024) return `${bytes} B`
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    return (
      <div
        ref={dropRef}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={cn(
          "relative rounded-xl border transition-colors",
          "bg-white border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/50",
          "focus-within:ring-2 focus-within:ring-eliza-red focus-within:border-transparent",
          isDragging && "ring-2 ring-eliza-red border-eliza-red bg-eliza-red/10 dark:bg-eliza-red/15",
          className
        )}
      >
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 px-3 pt-2">
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className={cn(
                  "relative group",
                  attachment.type === "image" && attachment.preview
                    ? "w-16 h-16"
                    : "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm bg-gray-100 dark:bg-dark-surface-2 text-charcoal dark:text-gray-200"
                )}
              >
                {attachment.type === "image" && attachment.preview ? (
                  <>
                    <img
                      src={attachment.preview}
                      alt={attachment.name}
                      className="w-full h-full object-cover rounded-lg"
                    />
                    <button
                      type="button"
                      onClick={() => removeAttachment(attachment.id)}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-800 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <XMarkIcon className="w-3 h-3" />
                    </button>
                  </>
                ) : (
                  <>
                    <DocumentIcon className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="max-w-[120px] truncate text-xs">{attachment.name}</span>
                    {attachment.size && (
                      <span className="text-[10px] text-gray-400">
                        {formatFileSize(attachment.size)}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeAttachment(attachment.id)}
                      className="p-0.5 hover:bg-gray-200 dark:hover:bg-dark-border rounded"
                    >
                      <XMarkIcon className="w-3 h-3 text-gray-500" />
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="flex items-center gap-2 px-3 py-2">
          <textarea
            ref={ref}
            value={currentValue}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className={cn(
              "flex-1 resize-none bg-transparent border-none outline-none focus:ring-0",
              "text-charcoal dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500",
              "text-sm min-h-[24px] max-h-[120px]",
              "[&:focus]:outline-none [&:focus]:ring-0 [&:focus]:border-none"
            )}
          />

          {showVoice && (
            <button
              type="button"
              onClick={onVoiceClick}
              disabled={disabled}
              className={cn(
                "p-1.5 rounded-lg transition-colors flex-shrink-0",
                "text-gray-400 hover:bg-gray-100 hover:text-gray-600",
                "dark:text-gray-500 dark:hover:bg-dark-surface-2 dark:hover:text-gray-300"
              )}
            >
              <MicrophoneIcon className="w-5 h-5" />
            </button>
          )}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={disabled || loading || (!currentValue.trim() && attachments.length === 0)}
            className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0",
              "bg-eliza-red text-white hover:bg-eliza-red-light",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {loading ? (
              <StopIcon className="w-4 h-4" />
            ) : (
              <ArrowUpIcon className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Bottom toolbar with file upload and tools */}
        <div className="flex items-center gap-2 px-2 pb-2 pt-0 flex-wrap">
          {/* File upload */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || attachments.length >= maxAttachments}
            className={cn(
              "flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-colors",
              "text-gray-500 hover:bg-gray-100 hover:text-gray-700",
              "dark:text-gray-400 dark:hover:bg-dark-surface-2 dark:hover:text-gray-200",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            <PaperClipIcon className="w-3.5 h-3.5" />
            <span>Attach</span>
          </button>

          {/* Tools dropdown */}
          {tools.length > 0 && (
            <div ref={toolsRef} className="relative flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setShowToolsMenu(!showToolsMenu)}
                disabled={disabled}
                className={cn(
                  "flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-colors",
                  "text-gray-500 hover:bg-gray-100 hover:text-gray-700",
                  "dark:text-gray-400 dark:hover:bg-dark-surface-2 dark:hover:text-gray-200",
                  selectedTools.length > 0 && "text-eliza-red dark:text-eliza-red"
                )}
              >
                <Cog6ToothIcon className="w-3.5 h-3.5" />
                <span>Tools</span>
                {selectedTools.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full bg-eliza-red text-white text-[10px] font-semibold leading-none">
                    {selectedTools.length}
                  </span>
                )}
                <ChevronDownIcon className={cn("w-3 h-3 transition-transform", showToolsMenu && "rotate-180")} />
              </button>

              {/* Tools dropdown menu */}
              {showToolsMenu && (
                <div
                  className={cn(
                    "absolute bottom-full left-0 mb-2 py-1 min-w-[220px] rounded-xl border shadow-lg",
                    "bg-white border-gray-200",
                    "dark:bg-dark-surface dark:border-dark-border/50"
                  )}
                >
                  <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Available Tools
                  </div>
                  {tools.map((tool) => {
                    const isSelected = selectedTools.includes(tool.id)
                    return (
                      <button
                        key={tool.id}
                        type="button"
                        onClick={() => toggleTool(tool.id)}
                        className={cn(
                          "w-full flex items-center gap-3 px-3 py-2 text-sm text-left",
                          "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
                          isSelected && "bg-eliza-red/5 dark:bg-eliza-red/10"
                        )}
                      >
                        <span className={cn(
                          "w-8 h-8 rounded-lg flex items-center justify-center",
                          isSelected
                            ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20 dark:text-white"
                            : "bg-gray-100 text-gray-600 dark:bg-dark-surface-2 dark:text-gray-400"
                        )}>
                          {tool.icon}
                        </span>
                        <div className="flex-1">
                          <p className={cn(
                            "font-medium",
                            isSelected ? "text-eliza-red dark:text-white" : "text-charcoal dark:text-gray-200"
                          )}>
                            {tool.name}
                          </p>
                          {tool.description && (
                            <p className="text-xs text-gray-500 dark:text-gray-400">{tool.description}</p>
                          )}
                        </div>
                        {isSelected && (
                          <CheckIcon className="w-4 h-4 text-eliza-red dark:text-white" />
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Selected tools - inline chips next to Tools button */}
          {selectedTools.length > 0 && (
            <>
              <div className="w-px h-4 bg-gray-200 dark:bg-dark-border/50" />
              {selectedTools.map((toolId) => {
                const tool = tools.find((t) => t.id === toolId)
                if (!tool) return null
                return (
                  <span
                    key={toolId}
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium",
                      "bg-eliza-red/10 text-eliza-red",
                      "dark:bg-eliza-red/20 dark:text-white"
                    )}
                  >
                    {tool.name}
                    <button
                      type="button"
                      onClick={() => toggleTool(toolId)}
                      className="hover:bg-eliza-red/20 rounded p-0.5 dark:hover:bg-eliza-red/30"
                    >
                      <XMarkIcon className="w-3 h-3" />
                    </button>
                  </span>
                )
              })}
            </>
          )}
        </div>

        {/* Drag overlay hint */}
        {isDragging && (
          <div className="absolute inset-0 flex items-center justify-center bg-eliza-red/10 dark:bg-eliza-red/20 rounded-xl pointer-events-none border-2 border-dashed border-eliza-red">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white dark:bg-dark-surface shadow-lg">
              <PaperClipIcon className="w-5 h-5 text-eliza-red" />
              <p className="text-sm font-medium text-eliza-red dark:text-white">Drop files here</p>
            </div>
          </div>
        )}
      </div>
    )
  }
)
PromptBarWithTools.displayName = "PromptBarWithTools"

/* ============================================
   PROMPT BAR WITH DOMAIN SELECTOR
   ============================================ */

interface Domain {
  id: string
  name: string
  description?: string
  icon?: React.ReactNode
}

interface PromptBarWithDomainProps extends PromptBarProps {
  /** Available domains */
  domains: Domain[]
  /** Currently selected domain */
  selectedDomain: string | null
  /** Callback when domain changes */
  onDomainChange: (domainId: string) => void
  /** Attachments for file upload */
  attachments?: Attachment[]
  onAttachmentsChange?: (attachments: Attachment[]) => void
  maxAttachments?: number
}

const PromptBarWithDomain = React.forwardRef<HTMLTextAreaElement, PromptBarWithDomainProps>(
  ({
    value,
    onChange,
    onSubmit,
    placeholder = "Ask a question about your data...",
    disabled,
    loading,
    domains,
    selectedDomain,
    onDomainChange,
    attachments = [],
    onAttachmentsChange,
    maxAttachments = 5,
    className,
  }, ref) => {
    const [internalValue, setInternalValue] = React.useState("")
    const [showDomainMenu, setShowDomainMenu] = React.useState(false)
    const [isDragging, setIsDragging] = React.useState(false)
    const domainRef = React.useRef<HTMLDivElement>(null)
    const fileInputRef = React.useRef<HTMLInputElement>(null)
    const dropRef = React.useRef<HTMLDivElement>(null)

    const currentValue = value ?? internalValue
    const selectedDomainObj = domains.find(d => d.id === selectedDomain)

    // Close domain menu on outside click
    React.useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (domainRef.current && !domainRef.current.contains(e.target as Node)) {
          setShowDomainMenu(false)
        }
      }
      document.addEventListener("mousedown", handleClickOutside)
      return () => document.removeEventListener("mousedown", handleClickOutside)
    }, [])

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value
      if (value === undefined) {
        setInternalValue(newValue)
      }
      onChange?.(newValue)
    }

    const handleSubmit = () => {
      if (currentValue.trim() && !disabled && !loading && selectedDomain) {
        onSubmit?.(currentValue)
        if (value === undefined) {
          setInternalValue("")
        }
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    }

    const processFiles = (files: FileList | null) => {
      if (!files || !onAttachmentsChange) return

      const newAttachments: Attachment[] = Array.from(files)
        .slice(0, maxAttachments - attachments.length)
        .map((file) => {
          const isImage = file.type.startsWith("image/")
          const attachment: Attachment = {
            id: Math.random().toString(36).substring(2, 9),
            name: file.name,
            type: isImage ? "image" : "file",
            size: file.size,
          }

          if (isImage) {
            const reader = new FileReader()
            reader.onload = (e) => {
              const preview = e.target?.result as string
              onAttachmentsChange?.(
                [...attachments, ...newAttachments].map((a) =>
                  a.id === attachment.id ? { ...a, preview } : a
                )
              )
            }
            reader.readAsDataURL(file)
          }

          return attachment
        })

      onAttachmentsChange?.([...attachments, ...newAttachments])
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      processFiles(e.target.files)
      e.target.value = ""
    }

    const handleDragEnter = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer.types.includes('Files')) {
        setIsDragging(true)
      }
    }

    const handleDragLeave = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      const rect = dropRef.current?.getBoundingClientRect()
      if (rect) {
        const { clientX, clientY } = e
        if (
          clientX <= rect.left ||
          clientX >= rect.right ||
          clientY <= rect.top ||
          clientY >= rect.bottom
        ) {
          setIsDragging(false)
        }
      }
    }

    const handleDragOver = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer.types.includes('Files')) {
        setIsDragging(true)
      }
    }

    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)
      processFiles(e.dataTransfer.files)
    }

    const removeAttachment = (id: string) => {
      onAttachmentsChange?.(attachments.filter((a) => a.id !== id))
    }

    const formatFileSize = (bytes: number): string => {
      if (bytes < 1024) return `${bytes} B`
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    const isSubmitDisabled = disabled || loading || !currentValue.trim() || !selectedDomain

    return (
      <div
        ref={dropRef}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={cn(
          "relative rounded-xl border transition-colors",
          "bg-white border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/50",
          "focus-within:ring-2 focus-within:ring-eliza-red focus-within:border-transparent",
          isDragging && "ring-2 ring-eliza-red border-eliza-red bg-eliza-red/10 dark:bg-eliza-red/15",
          className
        )}
      >
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 px-3 pt-2">
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className={cn(
                  "relative group",
                  attachment.type === "image" && attachment.preview
                    ? "w-16 h-16"
                    : "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm bg-gray-100 dark:bg-dark-surface-2 text-charcoal dark:text-gray-200"
                )}
              >
                {attachment.type === "image" && attachment.preview ? (
                  <>
                    <img
                      src={attachment.preview}
                      alt={attachment.name}
                      className="w-full h-full object-cover rounded-lg"
                    />
                    <button
                      type="button"
                      onClick={() => removeAttachment(attachment.id)}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-800 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <XMarkIcon className="w-3 h-3" />
                    </button>
                  </>
                ) : (
                  <>
                    <DocumentIcon className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="max-w-[120px] truncate text-xs">{attachment.name}</span>
                    {attachment.size && (
                      <span className="text-[10px] text-gray-400">
                        {formatFileSize(attachment.size)}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeAttachment(attachment.id)}
                      className="p-0.5 hover:bg-gray-200 dark:hover:bg-dark-border rounded"
                    >
                      <XMarkIcon className="w-3 h-3 text-gray-500" />
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="flex items-center gap-2 px-3 py-2">
          <textarea
            ref={ref}
            value={currentValue}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={selectedDomain ? placeholder : "Select a data domain to start..."}
            disabled={disabled || !selectedDomain}
            rows={1}
            className={cn(
              "flex-1 resize-none bg-transparent border-none outline-none focus:ring-0",
              "text-charcoal dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500",
              "text-sm min-h-[24px] max-h-[120px]",
              "[&:focus]:outline-none [&:focus]:ring-0 [&:focus]:border-none"
            )}
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitDisabled}
            className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0",
              "bg-eliza-red text-white hover:bg-eliza-red-light",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {loading ? (
              <StopIcon className="w-4 h-4" />
            ) : (
              <ArrowUpIcon className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Bottom toolbar with file upload and domain selector */}
        <div className="flex items-center gap-2 px-2 pb-2 pt-0">
          {/* File upload */}
          {onAttachmentsChange && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || attachments.length >= maxAttachments}
                className={cn(
                  "flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-colors",
                  "text-gray-500 hover:bg-gray-100 hover:text-gray-700",
                  "dark:text-gray-400 dark:hover:bg-dark-surface-2 dark:hover:text-gray-200",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                <PaperClipIcon className="w-3.5 h-3.5" />
                <span>Attach</span>
              </button>
            </>
          )}

          {/* Domain selector */}
          <div ref={domainRef} className="relative flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setShowDomainMenu(!showDomainMenu)}
              disabled={disabled}
              className={cn(
                "flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-colors",
                selectedDomain
                  ? "text-eliza-red dark:text-eliza-red bg-eliza-red/5 dark:bg-eliza-red/10"
                  : "text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-dark-surface-2 dark:hover:text-gray-200",
              )}
            >
              {selectedDomainObj?.icon || <CircleStackIcon className="w-3.5 h-3.5" />}
              <span>{selectedDomainObj?.name || "Select Domain"}</span>
              <ChevronDownIcon className={cn("w-3 h-3 transition-transform", showDomainMenu && "rotate-180")} />
            </button>

            {/* Domain dropdown menu */}
            {showDomainMenu && (
              <div
                className={cn(
                  "absolute bottom-full left-0 mb-2 py-1 min-w-[260px] rounded-xl border shadow-lg z-50",
                  "bg-white border-gray-200",
                  "dark:bg-dark-surface dark:border-dark-border/50"
                )}
              >
                <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Data Domains
                </div>
                {domains.map((domain) => {
                  const isSelected = selectedDomain === domain.id
                  return (
                    <button
                      key={domain.id}
                      type="button"
                      onClick={() => {
                        onDomainChange(domain.id)
                        setShowDomainMenu(false)
                      }}
                      className={cn(
                        "w-full flex items-center gap-3 px-3 py-2.5 text-sm text-left",
                        "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
                        isSelected && "bg-eliza-red/5 dark:bg-eliza-red/10"
                      )}
                    >
                      <span className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center",
                        isSelected
                          ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20 dark:text-white"
                          : "bg-gray-100 text-gray-600 dark:bg-dark-surface-2 dark:text-gray-400"
                      )}>
                        {domain.icon || <CircleStackIcon className="w-4 h-4" />}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className={cn(
                          "font-medium",
                          isSelected ? "text-eliza-red dark:text-white" : "text-charcoal dark:text-gray-200"
                        )}>
                          {domain.name}
                        </p>
                        {domain.description && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {domain.description}
                          </p>
                        )}
                      </div>
                      {isSelected && (
                        <CheckIcon className="w-4 h-4 text-eliza-red dark:text-white" />
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Drag overlay hint */}
        {isDragging && (
          <div className="absolute inset-0 flex items-center justify-center bg-eliza-red/10 dark:bg-eliza-red/20 rounded-xl pointer-events-none border-2 border-dashed border-eliza-red">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white dark:bg-dark-surface shadow-lg">
              <PaperClipIcon className="w-5 h-5 text-eliza-red" />
              <p className="text-sm font-medium text-eliza-red dark:text-white">Drop files here</p>
            </div>
          </div>
        )}
      </div>
    )
  }
)
PromptBarWithDomain.displayName = "PromptBarWithDomain"

/* ============================================
   EXPORTS
   ============================================ */

export {
  PromptBar,
  PromptBarWithAttachments,
  PromptBarWithTools,
  PromptBarWithDomain,
}
export type {
  PromptBarProps,
  PromptBarWithAttachmentsProps,
  PromptBarWithToolsProps,
  PromptBarWithDomainProps,
  Attachment,
  Tool,
  Domain,
}
