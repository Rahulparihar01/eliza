/**
 * New Home Page - Dashboard with Greeting, Search, and App Cards
 * 
 * Features:
 * - Personalized greeting with user's first name
 * - Semantic search / prompt bar
 * - App cards for navigating to different sections
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout } from '../../components/layout/Layout';
import { useAuth } from '../../contexts/AuthContext';
import { useAuth as useAuthStore } from '../../stores/useAuth';
import {
  Card,
  CardContent,
  Button,
  Badge,
  Input,
  PageContent,
  SectionHeader,
} from '../../components/ui';
import {
  ArrowUpIcon,
  SparklesIcon,
  UserGroupIcon,
  ChartBarIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  ArrowRightIcon,
  StarIcon as StarOutlineIcon,
  BeakerIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarSolidIcon } from '@heroicons/react/24/solid';
import { useFavorites } from '../../stores/useFavorites';
import { isAppletEnabled, isBaseChatPlatformEnabled, isFrontendAppEnabled } from '../../shared/lib/applets';

// App card configuration - Only actual "apps", not admin tools
// Each app has permissions that grant access (user needs ANY of them)
interface AppCard {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  iconKey: string; // For storing in favorites
  path: string;
  color: string;
  bgGradient: string;
  features?: string[];
  requiredPermissions: string[];
}

const appCards: AppCard[] = [
  {
    id: 'talent',
    title: 'AI Recruiter',
    description: 'Search for candidates, analyze talent pools, and generate personalized outreach.',
    icon: UserGroupIcon,
    iconKey: 'user-group',
    path: '/talent/analysis-config',
    color: 'text-rose-600',
    bgGradient: 'from-rose-500/10 to-rose-600/5',
    features: ['Talent Search', 'Candidate Scoring', 'Email Generation'],
    requiredPermissions: ['recruiter:config:read', 'recruiter:results:read', 'platform:admin'],
  },
  {
    id: 'chat',
    title: 'Chat',
    description: 'Chat with your data and documents using AI-powered assistants.',
    icon: ChatBubbleLeftRightIcon,
    iconKey: 'chat',
    path: '/chat',
    color: 'text-blue-600',
    bgGradient: 'from-blue-500/10 to-blue-600/5',
    features: ['Document Q&A', 'Data Analysis', 'Source Citations'],
    requiredPermissions: ['assistant:access', 'platform:admin'],
  },
  {
    id: 'workspaces',
    title: 'Workspaces',
    description: 'Create knowledge workspaces and upload documents for RAG-powered chat.',
    icon: DocumentTextIcon,
    iconKey: 'folder',
    path: '/workspaces',
    color: 'text-violet-600',
    bgGradient: 'from-violet-500/10 to-violet-600/5',
    features: ['Document Upload', 'Knowledge Bases', 'Workspace Management'],
    // TODO: Revisit granular permissions for workspaces (workspaces:read, workspaces:write)
    requiredPermissions: ['assistant:access', 'platform:admin'],
  },
  {
    id: 'adoption',
    title: 'Adoption Analytics',
    description: 'Track platform usage, user engagement, and feature adoption.',
    icon: ChartBarIcon,
    iconKey: 'chart-bar',
    path: '/adoption',
    color: 'text-emerald-600',
    bgGradient: 'from-emerald-500/10 to-emerald-600/5',
    features: ['Usage Metrics', 'Engagement Trends', 'Feature Adoption'],
    requiredPermissions: ['adoption:view_dashboard', 'platform:admin'],
  },
];

// Get time-based greeting
function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

// Get first name from user
function getFirstName(user: { first_name?: string; full_name?: string } | null | undefined): string {
  if (user?.first_name) return user.first_name;
  if (user?.full_name) {
    const parts = user.full_name.trim().split(' ');
    return parts[0] || 'there';
  }
  return 'there';
}

export default function NewHomePage() {
  const { user } = useAuth();
  const { hasAnyPermission } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');
  const { toggleFavorite, isFavorite } = useFavorites();
  const isRagEnabled = isBaseChatPlatformEnabled();
  const isAdoptionEnabled = isAppletEnabled('adoption');
  const isTalentEnabled = isAppletEnabled('talent');

  // Memoize filtered apps based on user permissions
  const accessibleApps = useMemo(() => {
    if (!user) return [];
    return appCards.filter(
      app => hasAnyPermission(app.requiredPermissions) && isFrontendAppEnabled(app.id)
    );
  }, [user, hasAnyPermission]);

  // Check if user can see Labs section
  const canSeeAgentConfig = hasAnyPermission(['labs:agents:access', 'platform:admin']);
  const canSeeResumeParsing = hasAnyPermission(['labs:resume_parsing:access', 'platform:admin']);
  const canSeeLabs = canSeeAgentConfig || canSeeResumeParsing;

  const greeting = getGreeting();
  const firstName = getFirstName(user);

  // Handle hash navigation for scrolling to apps section
  useEffect(() => {
    if (location.hash === '#apps') {
      // Small delay to ensure DOM is rendered
      const timer = setTimeout(() => {
        const appsSection = document.getElementById('apps-section');
        if (appsSection) {
          appsSection.scrollIntoView({ behavior: 'smooth' });
        }
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [location.hash]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // In modular mode, only route to pages that are enabled.
      if (isRagEnabled) {
        navigate(`/chat?q=${encodeURIComponent(searchQuery)}`);
      } else if (isAdoptionEnabled) {
        navigate('/adoption');
      }
    }
  };

  const handleQuickAction = (action: string) => {
    switch (action) {
      case 'job-spec':
        navigate('/talent/analysis-config');
        break;
      case 'talent-search':
        navigate('/talent/outreach');
        break;
      case 'analytics':
        navigate('/adoption');
        break;
    }
  };

  return (
    <Layout>
      <div className="h-full overflow-y-auto bg-gray-50 dark:bg-dark-bg">
        {/* Hero Section with Gradient + Greeting */}
        <div className="relative">
          {/* Gradient accent line */}
          <div className="h-1 bg-gradient-to-r from-eliza-red via-eliza-red-light to-eliza-red-coral" />
          
          {/* Hero content with gradient background */}
          <div className="bg-gradient-to-b from-eliza-red/5 to-transparent dark:from-eliza-red/10 dark:to-transparent">
            <div className="max-w-[1600px] mx-auto px-8 pt-10 pb-8">
              <div className="text-center max-w-2xl mx-auto">
                {/* Greeting - using DS title font */}
                <h1 className="font-title text-4xl md:text-5xl text-charcoal dark:text-white mb-8">
                  {greeting}, {firstName}.
                </h1>

                {/* Search / Prompt Bar */}
                <form onSubmit={handleSearch} className="relative mb-6">
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Ask a question or describe what you need..."
                    className="h-14 text-base rounded-2xl shadow-card border-gray-200 dark:border-gray-700 pr-14 pl-5"
                  />
                  <Button
                    type="submit"
                    variant="brand"
                    size="icon"
                    className="absolute right-2 top-1/2 -translate-y-1/2 shadow-lg"
                  >
                    <ArrowUpIcon className="h-5 w-5" />
                  </Button>
                </form>

                {/* Quick Actions */}
                <div className="flex flex-wrap justify-center gap-3">
                  {isTalentEnabled && (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleQuickAction('job-spec')}
                      >
                        <SparklesIcon className="h-4 w-4 text-eliza-red" />
                        Create job spec
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleQuickAction('talent-search')}
                      >
                        <UserGroupIcon className="h-4 w-4 text-eliza-red" />
                        Search talent pool
                      </Button>
                    </>
                  )}
                  {isAdoptionEnabled && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleQuickAction('analytics')}
                    >
                      <ChartBarIcon className="h-4 w-4 text-eliza-red" />
                      Pipeline analytics
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* App Cards Section */}
        <PageContent id="apps-section">
          <SectionHeader
            title="Your Apps"
            description="Quick access to your most-used applications"
          />
          
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
            {accessibleApps.map((app) => {
              const IconComponent = app.icon;
              const favorited = isFavorite(app.id);
              
              const handleToggleFavorite = (e: React.MouseEvent) => {
                e.stopPropagation(); // Prevent card navigation
                toggleFavorite({
                  id: app.id,
                  name: app.title,
                  path: app.path,
                  icon: app.iconKey,
                });
              };
              
              return (
                <Card 
                  key={app.id}
                  className="group cursor-pointer hover:shadow-lg transition-all duration-200 hover:-translate-y-0.5 overflow-hidden relative"
                  onClick={() => navigate(app.path)}
                >
                  {/* Favorite star button */}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleToggleFavorite}
                    className="absolute top-2 right-2 z-10 h-7 w-7 rounded-full bg-white/80 dark:bg-dark-surface/80 hover:bg-white dark:hover:bg-dark-surface shadow-sm hover:scale-110 transition-all duration-150"
                    title={favorited ? 'Remove from favorites' : 'Add to favorites'}
                  >
                    {favorited ? (
                      <StarSolidIcon className="h-4 w-4 text-amber-500" />
                    ) : (
                      <StarOutlineIcon className="h-4 w-4 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300" />
                    )}
                  </Button>
                  
                  {/* Gradient header */}
                  <div className={`h-20 bg-gradient-to-br ${app.bgGradient} flex items-center justify-center`}>
                    <div className={`p-3 rounded-xl bg-white/80 dark:bg-dark-surface/80 shadow-sm ${app.color}`}>
                      <IconComponent className="h-6 w-6" />
                    </div>
                  </div>
                  
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-subtitle text-charcoal dark:text-white group-hover:text-eliza-red transition-colors">
                        {app.title}
                      </h3>
                      <ArrowRightIcon className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 line-clamp-2">
                      {app.description}
                    </p>
                    
                    {app.features && (
                      <div className="flex flex-wrap gap-1.5">
                        {app.features.map((feature) => (
                          <Badge key={feature} variant="secondary" className="text-xs">
                            {feature}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

        </PageContent>

        {/* Labs Section - Only show if user has labs permissions */}
        {canSeeLabs && (
          <PageContent className="pt-0">
            <SectionHeader
              title="Labs"
              description="Experimental features and developer tools"
            />
            
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
              {/* Agent Configuration */}
              {canSeeAgentConfig && (
                <Card 
                  className="group cursor-pointer hover:shadow-lg transition-all duration-200 hover:-translate-y-0.5 overflow-hidden"
                  onClick={() => navigate('/admin/agents')}
                >
                  <div className="h-20 bg-gradient-to-br from-purple-500/10 to-purple-600/5 flex items-center justify-center">
                    <div className="p-3 rounded-xl bg-white/80 dark:bg-dark-surface/80 shadow-sm text-purple-600">
                      <CpuChipIcon className="h-6 w-6" />
                    </div>
                  </div>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-subtitle text-charcoal dark:text-white group-hover:text-eliza-red transition-colors">
                        Agent Configuration
                      </h3>
                      <ArrowRightIcon className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 line-clamp-2">
                      Configure AI agents, models, and provider settings.
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="info" className="text-xs">
                        Experimental
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Resume Parsing Test */}
              {canSeeResumeParsing && (
                <Card 
                  className="group cursor-pointer hover:shadow-lg transition-all duration-200 hover:-translate-y-0.5 overflow-hidden"
                  onClick={() => navigate('/admin/resume-parsing-test')}
                >
                  <div className="h-20 bg-gradient-to-br from-indigo-500/10 to-indigo-600/5 flex items-center justify-center">
                    <div className="p-3 rounded-xl bg-white/80 dark:bg-dark-surface/80 shadow-sm text-indigo-600">
                      <BeakerIcon className="h-6 w-6" />
                    </div>
                  </div>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-subtitle text-charcoal dark:text-white group-hover:text-eliza-red transition-colors">
                        Resume Parsing Test
                      </h3>
                      <ArrowRightIcon className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 line-clamp-2">
                      Test and debug resume parsing capabilities.
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="info" className="text-xs">
                        Developer Tool
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </PageContent>
        )}
      </div>
    </Layout>
  );
}
