/**
 * MainNavContent - Main Navigation Content
 * 
 * Simplified app-launcher style navigation.
 * - Home: Direct link
 * - Apps: Expandable menu showing available apps
 * - Favorites: User-pinned apps (alphabetically sorted)
 * 
 * Note: Admin section is now rendered in AppSidebar footer
 */

import React, { useMemo } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  HomeIcon,
  Squares2X2Icon,
  UserGroupIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  DocumentTextIcon,
  DocumentArrowDownIcon,
  PencilSquareIcon,
  StarIcon,
  SparklesIcon,
  FolderIcon,
  CurrencyDollarIcon,
  DocumentCheckIcon,
  HeartIcon,
  BuildingOffice2Icon,
  BanknotesIcon,
  ShieldExclamationIcon,
  AcademicCapIcon,
  EyeIcon,
  MegaphoneIcon,
  DocumentDuplicateIcon,
  WrenchScrewdriverIcon,
  TruckIcon,
  LightBulbIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  FireIcon,
  LinkIcon,
  PresentationChartBarIcon,
  CircleStackIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { cn } from '../../shared/lib/cn';
import { SidebarSection, SidebarItem } from '../ui/sidebar';
import { useFavorites } from '../../stores/useFavorites';
import { useAuth } from '../../stores/useAuth';
import { isFrontendAppEnabled } from '../../shared/lib/applets';

// Icon map for favorites (matches iconKey in app cards)
const favoriteIconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  'user-group': UserGroupIcon,
  'chat': ChatBubbleLeftRightIcon,
  'chart-bar': ChartBarIcon,
  'document': DocumentTextIcon,
  'sparkles': SparklesIcon,
  'folder': FolderIcon,
  'document-arrow-down': DocumentArrowDownIcon,
  'currency-dollar': CurrencyDollarIcon,
  'document-check': DocumentCheckIcon,
  'heart': HeartIcon,
  'building-office': BuildingOffice2Icon,
  'banknotes': BanknotesIcon,
  'shield-exclamation': ShieldExclamationIcon,
  'academic-cap': AcademicCapIcon,
  'eye': EyeIcon,
  'megaphone': MegaphoneIcon,
  'document-duplicate': DocumentDuplicateIcon,
  'wrench-screwdriver': WrenchScrewdriverIcon,
  'truck': TruckIcon,
  'light-bulb': LightBulbIcon,
  'chat-bubble-oval': ChatBubbleOvalLeftEllipsisIcon,
  'fire': FireIcon,
  'link': LinkIcon,
  'presentation-chart': PresentationChartBarIcon,
  'circle-stack': CircleStackIcon,
  'shield-check': ShieldCheckIcon,
};

// App definitions for the expandable Apps menu
// Each app has permissions that grant access (user needs ANY of them)
interface AppItem {
  id: string;
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  requiredPermissions: string[];
}

const appItems: AppItem[] = [
  {
    id: 'talent',
    label: 'AI Recruiter',
    path: '/talent/analysis-config',
    icon: UserGroupIcon,
    requiredPermissions: ['recruiter:config:read', 'recruiter:results:read', 'platform:admin'],
  },
  {
    id: 'chat',
    label: 'Chat',
    path: '/chat',
    icon: ChatBubbleLeftRightIcon,
    requiredPermissions: ['assistant:access', 'platform:admin'],
  },
  {
    id: 'workspaces',
    label: 'Workspaces',
    path: '/workspaces',
    icon: FolderIcon,
    // TODO: Revisit granular permissions for workspaces (workspaces:read, workspaces:write)
    requiredPermissions: ['assistant:access', 'platform:admin'],
  },
  {
    id: 'sow',
    label: 'SOW Automation',
    path: '/sow',
    icon: DocumentArrowDownIcon,
    requiredPermissions: ['assistant:access', 'platform:admin'],
  },
  {
    id: 'content-research',
    label: 'Content Research',
    path: '/content-research',
    icon: PencilSquareIcon,
    requiredPermissions: ['content_writer:read', 'content_writer:write', 'platform:admin'],
  },
  {
    id: 'adoption',
    label: 'Adoption Analytics',
    path: '/adoption',
    icon: ChartBarIcon,
    requiredPermissions: ['adoption:view_dashboard', 'platform:admin'],
  },
  {
    id: 'deal-intelligence',
    label: 'Deal Intelligence',
    path: '/deal-intelligence',
    icon: CurrencyDollarIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'rfp-responder',
    label: 'RFP Responder',
    path: '/rfp-responder',
    icon: DocumentCheckIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'customer-health',
    label: 'Customer Health Monitor',
    path: '/customer-health',
    icon: HeartIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'ma-analyst',
    label: 'M&A Analyst',
    path: '/ma-analyst',
    icon: BuildingOffice2Icon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'spend-optimizer',
    label: 'Spend Optimizer',
    path: '/spend-optimizer',
    icon: BanknotesIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'regulatory-radar',
    label: 'Regulatory Radar',
    path: '/regulatory-radar',
    icon: ShieldExclamationIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'onboarding-copilot',
    label: 'Onboarding Copilot',
    path: '/onboarding-copilot',
    icon: AcademicCapIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'competitive-intel',
    label: 'Competitive Intel',
    path: '/competitive-intel',
    icon: EyeIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'campaign-optimizer',
    label: 'Campaign Optimizer',
    path: '/campaign-optimizer',
    icon: MegaphoneIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'contract-hub',
    label: 'Contract Hub',
    path: '/contract-hub',
    icon: DocumentDuplicateIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'it-service-desk',
    label: 'IT Service Desk AI',
    path: '/it-service-desk',
    icon: WrenchScrewdriverIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'supply-chain',
    label: 'Supply Chain Monitor',
    path: '/supply-chain',
    icon: TruckIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'product-insights',
    label: 'Product Insights',
    path: '/product-insights',
    icon: LightBulbIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'eliza-engage',
    label: 'Eliza Engage',
    path: '/eliza-engage',
    icon: ChatBubbleOvalLeftEllipsisIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'incident-commander',
    label: 'Incident Commander',
    path: '/incident-commander',
    icon: FireIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'partner-intelligence',
    label: 'Partner Intelligence',
    path: '/partner-intelligence',
    icon: LinkIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'board-report-generator',
    label: 'Board Report Generator',
    path: '/board-report-generator',
    icon: PresentationChartBarIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'knowledge-miner',
    label: 'Knowledge Miner',
    path: '/knowledge-miner',
    icon: CircleStackIcon,
    requiredPermissions: ['platform:admin'],
  },
  {
    id: 'brand-guardian',
    label: 'Brand Guardian',
    path: '/brand-guardian',
    icon: ShieldCheckIcon,
    requiredPermissions: ['platform:admin'],
  },
];

/* ============================================
   Types
   ============================================ */

interface MainNavContentProps {
  /** Whether the sidebar is collapsed */
  collapsed?: boolean;
}

interface NavigationItem {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick?: () => void;
}

/* ============================================
   NavItem Component
   ============================================ */

interface NavItemProps {
  item: NavigationItem;
  collapsed: boolean;
  isActive?: boolean;
}

function NavItem({ item, collapsed, isActive = false }: NavItemProps) {
  const IconComponent = item.icon;

  // Item with custom onClick handler (e.g., Apps link)
  if (item.onClick) {
    return (
      <button
        onClick={item.onClick}
        className={cn(
          "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium",
          "transition-colors duration-150",
          "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
          isActive
            ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20"
            : "text-charcoal dark:text-gray-300",
          collapsed && "justify-center px-2"
        )}
        title={collapsed ? item.label : undefined}
      >
        <IconComponent className={cn(
          "h-5 w-5 flex-shrink-0",
          isActive ? "text-eliza-red" : "text-gray-500 dark:text-gray-400"
        )} />
        {!collapsed && <span className="flex-1 text-left truncate">{item.label}</span>}
      </button>
    );
  }

  // Regular navigation item (NavLink)
  return (
    <NavLink
      to={item.path}
      className={({ isActive: linkActive }) => cn(
        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium",
        "transition-colors duration-150",
        "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
        linkActive
          ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20"
          : "text-charcoal dark:text-gray-300",
        collapsed && "justify-center px-2"
      )}
      title={collapsed ? item.label : undefined}
    >
      {({ isActive: linkActive }) => (
        <>
          <IconComponent className={cn(
            "h-5 w-5 flex-shrink-0",
            linkActive ? "text-eliza-red" : "text-gray-500 dark:text-gray-400"
          )} />
          {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
        </>
      )}
    </NavLink>
  );
}

/* ============================================
   Main Navigation Content Component
   ============================================ */

export function MainNavContent({ collapsed = false }: MainNavContentProps) {
  const location = useLocation();
  const { getSortedFavorites } = useFavorites();
  const { user, hasAnyPermission } = useAuth();
  
  // Get favorites sorted alphabetically
  const favorites = getSortedFavorites();

  // Memoize filtered apps based on user permissions
  // Only recalculates when user permissions change
  const accessibleApps = useMemo(() => {
    if (!user) return [];
    return appItems.filter(
      app => hasAnyPermission(app.requiredPermissions) && isFrontendAppEnabled(app.id)
    );
  }, [user, hasAnyPermission]);

  // Check if any accessible app path is currently active
  const isAnyAppActive = accessibleApps.some(app => location.pathname.startsWith(app.path.split('/').slice(0, 2).join('/')));

  // Convert favorites to navigation items
  const favoriteItems: NavigationItem[] = favorites.map(fav => ({
    label: fav.name,
    path: fav.path,
    icon: favoriteIconMap[fav.icon] || StarIcon,
  }));

  return (
    <div className="flex flex-col h-full">
      {/* Top level items */}
      <div className="px-2 py-2 space-y-1">
        {/* Home - simple nav item */}
        <NavItem 
          item={{ label: 'Home', path: '/home', icon: HomeIcon }} 
          collapsed={collapsed}
        />
        
        {/* Apps - expandable menu (only shown if user has access to at least one app) */}
        {accessibleApps.length > 0 && (
          <SidebarItem
            icon={<Squares2X2Icon className="h-5 w-5" />}
            collapsed={collapsed}
            isActive={isAnyAppActive}
            defaultOpen={isAnyAppActive}
          >
            Apps
            {accessibleApps.map(app => {
              const isActive = location.pathname.startsWith(app.path.split('/').slice(0, 2).join('/'));
              const AppIcon = app.icon;
              return (
                <NavLink
                  key={app.id}
                  to={app.path}
                  className={({ isActive: linkActive }) => cn(
                    "flex items-center gap-2 w-full text-left py-2 pl-11 pr-3 text-sm rounded-r-lg transition-colors",
                    linkActive || isActive
                      ? "text-eliza-red font-medium bg-eliza-red/10 border-l-2 border-eliza-red dark:text-white dark:bg-eliza-red/20 dark:border-eliza-red"
                      : "text-gray-600 hover:text-charcoal hover:bg-gray-50 border-l-2 border-transparent dark:text-gray-400 dark:hover:text-white dark:hover:bg-dark-surface-2"
                  )}
                >
                  <AppIcon className={cn(
                    "h-4 w-4 flex-shrink-0",
                    isActive ? "text-eliza-red dark:text-white" : "text-gray-400"
                  )} />
                  <span className="truncate">{app.label}</span>
                </NavLink>
              );
            })}
          </SidebarItem>
        )}
      </div>

      {/* Favorites Section - Only shown when user has favorites */}
      {favoriteItems.length > 0 && (
        <SidebarSection title="FAVORITES" collapsed={collapsed}>
          {favoriteItems.map(item => (
            <NavItem key={item.path} item={item} collapsed={collapsed} />
          ))}
        </SidebarSection>
      )}
    </div>
  );
}

export default MainNavContent;
