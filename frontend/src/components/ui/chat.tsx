/**
 * Chat Components - Eliza Forge Design System
 * 
 * A complete set of chat UI components including:
 * - Message bubbles (user/assistant)
 * - Chat container with scroll management
 * - Thinking indicators with expandable traces
 * - Image attachments
 * - Canvas/Artifact panel
 */

import * as React from "react"
import { 
  ChevronDownIcon, 
  ChevronRightIcon,
  XMarkIcon,
  SparklesIcon,
  UserIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  PhotoIcon,
  ChartBarIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  ClipboardDocumentIcon,
  CheckIcon,
} from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"
import { cva, type VariantProps } from "class-variance-authority"

/* ============================================
   CHAT CONTEXT (for canvas state)
   ============================================ */

interface ChatContextValue {
  canvasOpen: boolean
  setCanvasOpen: (open: boolean) => void
  canvasContent: React.ReactNode | null
  setCanvasContent: (content: React.ReactNode | null) => void
  canvasTitle: string
  setCanvasTitle: (title: string) => void
  canvasHeaderActions: React.ReactNode | null
  setCanvasHeaderActions: (actions: React.ReactNode | null) => void
}

const ChatContext = React.createContext<ChatContextValue | undefined>(undefined)

const useChat = () => {
  const context = React.useContext(ChatContext)
  if (!context) {
    throw new Error("useChat must be used within a ChatProvider")
  }
  return context
}

/* ============================================
   CHAT PROVIDER
   ============================================ */

interface ChatProviderProps {
  children: React.ReactNode
}

const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [canvasOpen, setCanvasOpen] = React.useState(false)
  const [canvasContent, setCanvasContent] = React.useState<React.ReactNode | null>(null)
  const [canvasTitle, setCanvasTitle] = React.useState("")
  const [canvasHeaderActions, setCanvasHeaderActions] = React.useState<React.ReactNode | null>(null)

  return (
    <ChatContext.Provider value={{ 
      canvasOpen, 
      setCanvasOpen, 
      canvasContent, 
      setCanvasContent,
      canvasTitle,
      setCanvasTitle,
      canvasHeaderActions,
      setCanvasHeaderActions,
    }}>
      {children}
    </ChatContext.Provider>
  )
}

/* ============================================
   CHAT CONTAINER
   ============================================ */

interface ChatContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

const ChatContainer = React.forwardRef<HTMLDivElement, ChatContainerProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex h-full w-full min-w-0 overflow-hidden",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
ChatContainer.displayName = "ChatContainer"

/* ============================================
   CHAT MESSAGES PANE
   ============================================ */

interface ChatMessagesPaneProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

const ChatMessagesPane = React.forwardRef<HTMLDivElement, ChatMessagesPaneProps>(
  ({ className, children, ...props }, ref) => {
    const context = React.useContext(ChatContext)
    const canvasOpen = context?.canvasOpen ?? false

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex flex-col flex-1 h-full min-w-0 overflow-hidden",
          "transition-all duration-300 ease-in-out",
          canvasOpen && "mr-0",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
ChatMessagesPane.displayName = "ChatMessagesPane"

/* ============================================
   CHAT HEADER
   ============================================ */

interface ChatHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

/**
 * ChatHeader - Optional header inside the chat pane
 * 
 * Use this for domain selectors, breadcrumbs, or other context
 * that should stay visible above the scrolling messages.
 * Transparent by default to blend with chat background.
 */
const ChatHeader = React.forwardRef<HTMLDivElement, ChatHeaderProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center gap-3 px-4 py-2",
          "flex-shrink-0",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
ChatHeader.displayName = "ChatHeader"

/* ============================================
   CHAT SCROLL AREA
   ============================================ */

interface ChatScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  /** Auto-scroll to bottom on new messages */
  autoScroll?: boolean
}

const ChatScrollArea = React.forwardRef<HTMLDivElement, ChatScrollAreaProps>(
  ({ className, children, autoScroll = true, ...props }, ref) => {
    const scrollRef = React.useRef<HTMLDivElement>(null)
    const [isAtBottom, setIsAtBottom] = React.useState(true)

    // Combine refs
    React.useImperativeHandle(ref, () => scrollRef.current!)

    // Auto-scroll effect
    React.useEffect(() => {
      if (autoScroll && isAtBottom && scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight
      }
    }, [children, autoScroll, isAtBottom])

    const handleScroll = () => {
      if (scrollRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
        setIsAtBottom(scrollHeight - scrollTop - clientHeight < 50)
      }
    }

    return (
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={cn(
          "flex-1 overflow-y-auto",
          "px-4 py-6",
          className
        )}
        {...props}
      >
        {/* pl-12 provides space for absolutely positioned assistant avatars */}
        <div className="max-w-3xl mx-auto space-y-6 pl-12">
          {children}
        </div>
      </div>
    )
  }
)
ChatScrollArea.displayName = "ChatScrollArea"

/* ============================================
   MESSAGE BUBBLE
   ============================================ */

const messageBubbleVariants = cva(
  "",
  {
    variants: {
      role: {
        user: [
          "rounded-2xl px-4 py-3",
          "ml-auto",
          "bg-gray-100 text-charcoal",
          "dark:bg-dark-surface-2 dark:text-gray-100",
          "rounded-br-md",
        ],
        assistant: [
          // No bubble - just text like ChatGPT
          "mr-auto",
          "text-charcoal dark:text-gray-100",
        ],
        system: [
          "rounded-2xl px-4 py-3",
          "mx-auto text-center",
          "bg-gray-50 text-gray-500",
          "dark:bg-dark-surface dark:text-gray-400",
          "text-sm",
        ],
      },
    },
    defaultVariants: {
      role: "assistant",
    },
  }
)

interface MessageBubbleProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'role'> {
  children: React.ReactNode
  /** Message role */
  role?: "user" | "assistant" | "system"
  /** Show avatar */
  showAvatar?: boolean
  /** Avatar content (initials or image) */
  avatar?: React.ReactNode
  /** Timestamp */
  timestamp?: string
  /** Is this message being streamed */
  isStreaming?: boolean
}

const MessageBubble = React.forwardRef<HTMLDivElement, MessageBubbleProps>(
  ({ className, role = "assistant", children, showAvatar, avatar, timestamp, isStreaming, ...props }, ref) => {
    const isUser = role === "user"
    const isSystem = role === "system"
    
    // Default: show avatar for assistant, not for user
    const shouldShowAvatar = showAvatar ?? (role === "assistant")

    if (isSystem) {
      return (
        <div
          ref={ref}
          className={cn(messageBubbleVariants({ role }), className)}
          {...props}
        >
          {children}
        </div>
      )
    }

    return (
      <div
        ref={ref}
        className={cn(
          "relative",
          isUser ? "flex flex-row-reverse gap-3" : "flex flex-col gap-1",
          className
        )}
        {...props}
      >
        {/* Avatar - positioned absolutely for assistant to avoid content shift */}
        {shouldShowAvatar && !isUser && (
          <div className={cn(
            "absolute -left-10 top-0",
            "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
            "bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400"
          )}>
            {avatar || <SparklesIcon className="w-4 h-4" />}
          </div>
        )}
        
        {/* Avatar - inline for user messages */}
        {shouldShowAvatar && isUser && (
          <div className={cn(
            "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
            "bg-eliza-red/20 text-eliza-red"
          )}>
            {avatar || <UserIcon className="w-4 h-4" />}
          </div>
        )}

        {/* Message content */}
        <div className={cn(
          "flex flex-col gap-1",
          isUser ? "items-end max-w-[85%]" : "items-start w-full"
        )}>
          <div className={cn(messageBubbleVariants({ role }), "max-w-none")}>
            {children}
            {isStreaming && (
              <span className="inline-block w-0.5 h-4 ml-0.5 bg-current opacity-75 animate-pulse" />
            )}
          </div>
          {timestamp && (
            <span className={cn(
              "text-xs text-gray-400",
              isUser ? "text-right" : "text-left"
            )}>
              {timestamp}
            </span>
          )}
        </div>
      </div>
    )
  }
)
MessageBubble.displayName = "MessageBubble"

/* ============================================
   MESSAGE CONTENT (Markdown-ready)
   ============================================ */

interface MessageContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

const MessageContent = React.forwardRef<HTMLDivElement, MessageContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "prose prose-sm dark:prose-invert max-w-none",
          "prose-p:my-2 prose-p:leading-relaxed",
          "prose-pre:bg-gray-900 prose-pre:text-gray-100",
          "prose-code:text-eliza-red prose-code:bg-gray-100 prose-code:dark:bg-dark-surface prose-code:px-1 prose-code:rounded",
          "prose-a:text-eliza-red prose-a:no-underline hover:prose-a:underline",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
MessageContent.displayName = "MessageContent"

/* ============================================
   THINKING INDICATOR
   ============================================ */

interface ExecutionStep {
  /** Unique step identifier */
  id: string
  /** Display label for the step */
  label: string
  /** Current status */
  status: 'pending' | 'active' | 'completed' | 'failed'
  /** Optional description/detail text */
  description?: string
  /** Timestamp when completed */
  timestamp?: Date
}

interface ThinkingIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Thinking text/trace content */
  thinkingText?: string
  /** Is expandable to show thinking trace */
  expandable?: boolean
  /** Default expanded state */
  defaultExpanded?: boolean
  /** Label text (shimmer header) */
  label?: string
  /** Execution steps to display as checklist */
  steps?: ExecutionStep[]
  /** Whether to show the steps section expanded by default */
  stepsDefaultExpanded?: boolean
  /** Hide the avatar */
  hideAvatar?: boolean
  /** Whether the thinking process is complete (stops shimmer, shows static label) */
  isComplete?: boolean
  /** Label to show when complete (defaults to "Analysis complete") */
  completeLabel?: string
}

const ThinkingIndicator = React.forwardRef<HTMLDivElement, ThinkingIndicatorProps>(
  ({ 
    className, 
    thinkingText, 
    expandable = false, 
    defaultExpanded = false, 
    label = "Thinking",
    steps,
    stepsDefaultExpanded = true,
    hideAvatar = false,
    isComplete = false,
    completeLabel = "Analysis complete",
    ...props 
  }, ref) => {
    const [expanded, setExpanded] = React.useState(defaultExpanded)
    const [stepsExpanded, setStepsExpanded] = React.useState(stepsDefaultExpanded)

    // Find current active step for shimmer label
    const activeStep = steps?.find(s => s.status === 'active')
    
    // Determine display label based on state
    const displayLabel = isComplete 
      ? completeLabel 
      : (activeStep?.label || label)

    // Check if process is done: all steps complete, OR any step failed (stops the pipeline)
    const hasFailedStep = steps?.some(s => s.status === 'failed') ?? false
    const allStepsComplete = steps?.length ? steps.every(s => s.status === 'completed') : false
    const showAsComplete = isComplete || allStepsComplete || hasFailedStep

    return (
      <div
        ref={ref}
        className={cn(
          "flex gap-3",
          className
        )}
        {...props}
      >
        {/* Avatar */}
        {!hideAvatar && (
          <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-gray-100 dark:bg-dark-surface-2">
            <SparklesIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
          </div>
        )}

        {/* Thinking content */}
        <div className="flex-1 pt-1">
          {/* Header with shimmer text or static complete text */}
          <button
            onClick={() => {
              if (expandable) setExpanded(!expanded)
              else if (steps && steps.length > 0) setStepsExpanded(!stepsExpanded)
            }}
            className={cn(
              "flex items-center gap-2",
              (expandable || (steps && steps.length > 0)) && "cursor-pointer hover:opacity-80"
            )}
            disabled={!expandable && (!steps || steps.length === 0)}
          >
            {showAsComplete ? (
              /* Static complete label - no shimmer */
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {displayLabel}
              </span>
            ) : (
              /* Shimmer text effect - gradient sweeps left to right */
              <span 
                className="text-sm relative overflow-hidden"
                style={{
                  background: "linear-gradient(90deg, #9ca3af 0%, #9ca3af 40%, #d1d5db 50%, #9ca3af 60%, #9ca3af 100%)",
                  backgroundSize: "200% 100%",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  animation: "shimmer-text 2s ease-in-out infinite",
                }}
              >
                {displayLabel}
              </span>
            )}

            {(expandable || (steps && steps.length > 0)) && (
              <ChevronRightIcon className={cn(
                "w-3.5 h-3.5 text-gray-400 transition-transform duration-200",
                (expandable ? expanded : stepsExpanded) && "rotate-90"
              )} />
            )}
          </button>

          {/* Execution Steps Checklist */}
          {steps && steps.length > 0 && (
            <div className={cn(
              "overflow-hidden transition-all duration-300",
              stepsExpanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
            )}>
              <div className={cn(
                "mt-3 space-y-2",
              )}>
                {steps.map((step, index) => (
                  <div 
                    key={step.id} 
                    className={cn(
                      "flex items-start gap-3 text-sm",
                      step.status === 'completed' && "text-gray-400 dark:text-gray-500",
                      step.status === 'active' && "text-charcoal dark:text-gray-100",
                      step.status === 'pending' && "text-gray-400 dark:text-gray-500",
                      step.status === 'failed' && "text-gray-400 dark:text-gray-500",
                    )}
                  >
                    {/* Step indicator */}
                    <div className="flex-shrink-0 mt-0.5">
                      {step.status === 'completed' && (
                        <div className="w-5 h-5 rounded-full bg-green-100 dark:bg-green-500/20 flex items-center justify-center">
                          <CheckIcon className="w-3 h-3 text-green-600 dark:text-green-400" />
                        </div>
                      )}
                      {step.status === 'active' && (
                        <div className="w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center">
                          <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                        </div>
                      )}
                      {step.status === 'pending' && (
                        <div className="w-5 h-5 rounded-full bg-gray-100 dark:bg-dark-surface-2 flex items-center justify-center">
                          <div className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600" />
                        </div>
                      )}
                      {step.status === 'failed' && (
                        <div className="w-5 h-5 rounded-full bg-red-100 dark:bg-red-500/20 flex items-center justify-center">
                          <XMarkIcon className="w-3 h-3 text-red-600 dark:text-red-400" />
                        </div>
                      )}
                    </div>
                    
                    {/* Step content */}
                    <div className="flex-1 min-w-0">
                      <span className={cn(
                        "font-medium",
                        step.status === 'completed' && "text-gray-500 dark:text-gray-400",
                        step.status === 'active' && "text-charcoal dark:text-gray-100",
                        step.status === 'pending' && "text-gray-400 dark:text-gray-500",
                        step.status === 'failed' && "text-gray-500 dark:text-gray-400",
                      )}>
                        {step.label}
                      </span>
                      {step.description && (
                        <p className={cn(
                          "text-xs mt-0.5",
                          step.status === 'completed' && "text-gray-400 dark:text-gray-500",
                          step.status === 'active' && "text-gray-500 dark:text-gray-400",
                          step.status === 'pending' && "text-gray-400 dark:text-gray-500",
                          step.status === 'failed' && "text-gray-400 dark:text-gray-500",
                        )}>
                          {step.description}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Expandable thinking trace */}
          {expandable && thinkingText && (
            <div className={cn(
              "overflow-hidden transition-all duration-300",
              expanded ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
            )}>
              <div className={cn(
                "mt-2 p-3 rounded-lg",
                "bg-gray-50 dark:bg-dark-surface",
                "border border-gray-100 dark:border-dark-border/30",
                "text-sm text-gray-600 dark:text-gray-400",
                "leading-relaxed",
                "max-h-64 overflow-y-auto"
              )}>
                <div className="whitespace-pre-wrap">{thinkingText}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }
)
ThinkingIndicator.displayName = "ThinkingIndicator"

/* ============================================
   CHAT IMAGE
   ============================================ */

interface ChatImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  /** Alt text */
  alt: string
  /** Caption */
  caption?: string
  /** Click to open in canvas */
  openInCanvas?: boolean
}

const ChatImage = React.forwardRef<HTMLImageElement, ChatImageProps>(
  ({ className, src, alt, caption, openInCanvas = true, ...props }, ref) => {
    const context = React.useContext(ChatContext)
    const [loaded, setLoaded] = React.useState(false)

    const handleOpenInCanvas = () => {
      if (openInCanvas && context) {
        context.setCanvasTitle(caption || alt)
        context.setCanvasContent(
          <div className="flex items-center justify-center h-full p-4">
            <img src={src} alt={alt} className="max-w-full max-h-full object-contain rounded-lg" />
          </div>
        )
        context.setCanvasOpen(true)
      }
    }

    return (
      <div className={cn("my-2", className)}>
        <div className="relative group">
          {/* Loading skeleton */}
          {!loaded && (
            <div className="w-full h-48 bg-gray-200 dark:bg-dark-surface-2 rounded-lg animate-pulse" />
          )}
          
          <img
            ref={ref}
            src={src}
            alt={alt}
            onLoad={() => setLoaded(true)}
            className={cn(
              "rounded-lg max-w-full cursor-pointer",
              "transition-opacity duration-200",
              loaded ? "opacity-100" : "opacity-0 absolute inset-0",
              "hover:opacity-90"
            )}
            onClick={handleOpenInCanvas}
            {...props}
          />

          {/* Expand button overlay */}
          {loaded && openInCanvas && context && (
            <button
              onClick={handleOpenInCanvas}
              className={cn(
                "absolute top-2 right-2",
                "p-1.5 rounded-md",
                "bg-black/50 text-white",
                "opacity-0 group-hover:opacity-100",
                "transition-opacity duration-200"
              )}
            >
              <ArrowsPointingOutIcon className="w-4 h-4" />
            </button>
          )}
        </div>
        
        {caption && (
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{caption}</p>
        )}
      </div>
    )
  }
)
ChatImage.displayName = "ChatImage"

/* ============================================
   CODE BLOCK (for chat)
   ============================================ */

interface ChatCodeBlockProps extends React.HTMLAttributes<HTMLDivElement> {
  code: string
  language?: string
  filename?: string
  /** Show open in canvas button */
  showCanvasButton?: boolean
}

const ChatCodeBlock = React.forwardRef<HTMLDivElement, ChatCodeBlockProps>(
  ({ className, code, language = "plaintext", filename, showCanvasButton = true, ...props }, ref) => {
    const context = React.useContext(ChatContext)
    const [copied, setCopied] = React.useState(false)

    const handleCopy = async () => {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }

    const handleOpenInCanvas = () => {
      if (context) {
        context.setCanvasTitle(filename || `${language} code`)
        context.setCanvasContent(
          <div className="h-full flex flex-col">
            <div className="flex-1 overflow-auto p-4">
              <pre className="text-sm font-mono text-gray-100 whitespace-pre-wrap">{code}</pre>
            </div>
          </div>
        )
        context.setCanvasOpen(true)
      }
    }

    return (
      <div
        ref={ref}
        className={cn("my-2 rounded-lg overflow-hidden", className)}
        {...props}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-gray-800 dark:bg-gray-900">
          <div className="flex items-center gap-2">
            <CodeBracketIcon className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-400">{filename || language}</span>
          </div>
          <div className="flex items-center gap-1">
            {showCanvasButton && context && (
              <button
                onClick={handleOpenInCanvas}
                className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
                title="Open in canvas"
              >
                <ArrowsPointingOutIcon className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={handleCopy}
              className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              title="Copy code"
            >
              {copied ? (
                <CheckIcon className="w-4 h-4 text-green-400" />
              ) : (
                <ClipboardDocumentIcon className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Code */}
        <div className="p-4 bg-gray-900 overflow-x-auto">
          <pre className="text-sm font-mono text-gray-100 whitespace-pre-wrap">{code}</pre>
        </div>
      </div>
    )
  }
)
ChatCodeBlock.displayName = "ChatCodeBlock"

/* ============================================
   ARTIFACT / CANVAS PANEL (Resizable)
   ============================================ */

interface CanvasPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Initial width as percentage (default: 50) */
  defaultWidthPercent?: number
  /** Minimum width as percentage */
  minWidthPercent?: number
  /** Maximum width as percentage */
  maxWidthPercent?: number
}

const CanvasPanel = React.forwardRef<HTMLDivElement, CanvasPanelProps>(
  ({ className, defaultWidthPercent = 50, minWidthPercent = 20, maxWidthPercent = 80, ...props }, ref) => {
    const context = React.useContext(ChatContext)
    const [isFullscreen, setIsFullscreen] = React.useState(false)
    const [widthPercent, setWidthPercent] = React.useState(defaultWidthPercent)
    const [isResizing, setIsResizing] = React.useState(false)
    const panelRef = React.useRef<HTMLDivElement>(null)

    // Handle mouse move for resizing - must be before any early returns
    React.useEffect(() => {
      const handleMouseMove = (e: MouseEvent) => {
        if (!isResizing || !panelRef.current) return
        
        const containerRect = panelRef.current.parentElement?.getBoundingClientRect()
        if (!containerRect) return
        
        // Calculate new width as percentage of container
        const newWidthPx = containerRect.right - e.clientX
        const newWidthPercent = (newWidthPx / containerRect.width) * 100
        
        // Clamp to min/max percentages
        const clampedPercent = Math.min(Math.max(newWidthPercent, minWidthPercent), maxWidthPercent)
        setWidthPercent(clampedPercent)
      }

      const handleMouseUp = () => {
        setIsResizing(false)
      }

      if (isResizing) {
        document.addEventListener('mousemove', handleMouseMove)
        document.addEventListener('mouseup', handleMouseUp)
        // Prevent text selection while dragging
        document.body.style.userSelect = 'none'
        document.body.style.cursor = 'ew-resize'
      }

      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
      }
    }, [isResizing, minWidthPercent, maxWidthPercent])

    if (!context) return null

    const { canvasOpen, setCanvasOpen, canvasContent, canvasTitle, canvasHeaderActions, setCanvasHeaderActions } = context

    // Handle close - clear all canvas state
    const handleClose = () => {
      setCanvasOpen(false)
      setIsFullscreen(false)
      setCanvasHeaderActions(null)
    }

    // Handle mouse down on resize handle
    const handleMouseDown = (e: React.MouseEvent) => {
      e.preventDefault()
      setIsResizing(true)
    }

    // Calculate display width - check canvasOpen first to ensure panel collapses when closed
    const displayWidth = !canvasOpen ? 0 : (isFullscreen ? '100%' : `${widthPercent}%`)

    return (
      <div
        ref={(node) => {
          // Handle both refs
          (panelRef as React.MutableRefObject<HTMLDivElement | null>).current = node
          if (typeof ref === 'function') ref(node)
          else if (ref) ref.current = node
        }}
        style={{
          width: displayWidth,
          maxWidth: isFullscreen ? '100%' : displayWidth, // Enforce width as max to prevent content from pushing wider
          minWidth: canvasOpen && !isFullscreen ? `${minWidthPercent}%` : undefined,
          flexBasis: isFullscreen ? '100%' : displayWidth,
        }}
        className={cn(
          "h-full overflow-hidden flex-shrink-0 flex-grow-0 relative",
          // Theme-aware background
          "bg-white dark:bg-dark-surface",
          "border-l border-gray-200 dark:border-dark-border/50",
          // Only animate when not resizing
          !isResizing && "transition-all duration-300 ease-in-out",
          // Only apply fullscreen when BOTH open and fullscreen are true
          isFullscreen && canvasOpen && "fixed inset-0 z-50",
          className
        )}
        {...props}
      >
        {canvasOpen && (
          <>
            {/* Resize Handle - Left Edge */}
            {!isFullscreen && (
              <div
                onMouseDown={handleMouseDown}
                className={cn(
                  "absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize z-10",
                  "hover:bg-eliza-red/30 active:bg-eliza-red/50",
                  "transition-colors",
                  isResizing && "bg-eliza-red/50"
                )}
                title="Drag to resize"
              />
            )}

            <div className="flex flex-col h-full w-full min-w-0 overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-dark-border/50 bg-gray-50 dark:bg-dark-surface-2 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <DocumentTextIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                  <span className="text-sm font-medium text-charcoal dark:text-gray-100 truncate max-w-[200px]">
                    {canvasTitle || "Canvas"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {/* Content-specific header actions */}
                  {canvasHeaderActions}
                  
                  {/* Divider when there are header actions */}
                  {canvasHeaderActions && (
                    <div className="w-px h-5 bg-gray-200 dark:bg-dark-border/50" />
                  )}
                  
                  <button
                    onClick={() => setIsFullscreen(!isFullscreen)}
                    className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-dark-surface-3 text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-white transition-colors"
                    title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                  >
                    {isFullscreen ? (
                      <ArrowsPointingInIcon className="w-4 h-4" />
                    ) : (
                      <ArrowsPointingOutIcon className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={handleClose}
                    className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-dark-surface-3 text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-white transition-colors"
                    title="Close"
                  >
                    <XMarkIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Content - edge-to-edge, content components add their own padding if needed */}
              <div className="flex-1 overflow-hidden bg-white dark:bg-dark-surface min-w-0 min-h-0">
                <div className="w-full h-full min-w-0 overflow-auto">
                  {canvasContent}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    )
  }
)
CanvasPanel.displayName = "CanvasPanel"

/* ============================================
   ARTIFACT BUTTON (inline in messages)
   ============================================ */

interface ArtifactButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'type'> {
  /** Artifact type */
  artifactType?: "code" | "image" | "document" | "chart"
  /** Title */
  title: string
  /** Description */
  description?: string
  /** Content to show in canvas */
  canvasContent: React.ReactNode
}

const ArtifactButton = React.forwardRef<HTMLButtonElement, ArtifactButtonProps>(
  ({ className, artifactType = "document", title, description, canvasContent, ...props }, ref) => {
    const context = React.useContext(ChatContext)

    const icons = {
      code: CodeBracketIcon,
      image: PhotoIcon,
      document: DocumentTextIcon,
      chart: ChartBarIcon,
    }
    const Icon = icons[artifactType]

    const handleClick = () => {
      if (context) {
        context.setCanvasTitle(title)
        context.setCanvasContent(canvasContent)
        context.setCanvasOpen(true)
      }
    }

    return (
      <button
        ref={ref}
        onClick={handleClick}
        className={cn(
          "flex items-center gap-3 p-3 rounded-lg w-full text-left",
          "border border-gray-200 dark:border-dark-border/50",
          "bg-white dark:bg-dark-surface",
          "hover:border-eliza-red/50 hover:bg-gray-50 dark:hover:bg-dark-surface-2",
          "transition-colors duration-150",
          "group",
          className
        )}
        {...props}
      >
        <div className={cn(
          "flex items-center justify-center w-10 h-10 rounded-lg",
          "bg-gray-100 dark:bg-dark-surface-2",
          "group-hover:bg-eliza-red/10",
          "transition-colors duration-150"
        )}>
          <Icon className="w-5 h-5 text-gray-500 dark:text-gray-400 group-hover:text-eliza-red" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-charcoal dark:text-white truncate">
            {title}
          </p>
          {description && (
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
              {description}
            </p>
          )}
        </div>
        <ArrowsPointingOutIcon className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
      </button>
    )
  }
)
ArtifactButton.displayName = "ArtifactButton"

/* ============================================
   CHAT INPUT AREA (wrapper for PromptBar)
   ============================================ */

interface ChatInputAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

const ChatInputArea = React.forwardRef<HTMLDivElement, ChatInputAreaProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          // No background - prompt bar floats above content
          "p-4 pb-6",
          className
        )}
        {...props}
      >
        <div className="max-w-3xl mx-auto">
          {children}
        </div>
      </div>
    )
  }
)
ChatInputArea.displayName = "ChatInputArea"

/* ============================================
   EXPORTS
   ============================================ */

export {
  // Context
  ChatProvider,
  useChat,
  // Layout
  ChatContainer,
  ChatMessagesPane,
  ChatHeader,
  ChatScrollArea,
  ChatInputArea,
  // Messages
  MessageBubble,
  MessageContent,
  messageBubbleVariants,
  // Indicators
  ThinkingIndicator,
  // Media
  ChatImage,
  ChatCodeBlock,
  // Canvas
  CanvasPanel,
  ArtifactButton,
}

export type {
  ChatContainerProps,
  ChatMessagesPaneProps,
  ChatHeaderProps,
  ChatScrollAreaProps,
  MessageBubbleProps,
  ThinkingIndicatorProps,
  ExecutionStep,
  ChatImageProps,
  ChatCodeBlockProps,
  CanvasPanelProps,
  ArtifactButtonProps,
}
