/**
 * Dashboard Page - AI Enablement Platform
 * 
 * Main dashboard with overview metrics, recent activity, and quick actions
 * Following the Linear-style design system from UX specification.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  DocumentTextIcon,
  CloudArrowUpIcon,
  MagnifyingGlassIcon,
  ChartBarIcon,
  UsersIcon,
  CpuChipIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import { DashboardLayout } from '../../components/layout/Layout';
import { useAuth } from '../../contexts/AuthContext';

// Local type for dashboard metrics (mock data)
interface MetricCard {
  title: string;
  value: string;
  change?: {
    value: number;
    trend: 'up' | 'down';
    period: string;
  };
  icon: string;
  color: string;
}

// Mock data - replace with real API calls
const mockMetrics: MetricCard[] = [
  {
    title: 'Total Documents',
    value: '2,847',
    change: { value: 12, trend: 'up', period: 'vs last month' },
    icon: 'document',
    color: 'brand',
  },
  {
    title: 'Processing Queue',
    value: '23',
    change: { value: 5, trend: 'down', period: 'vs yesterday' },
    icon: 'clock',
    color: 'ai-warning',
  },
  {
    title: 'Search Queries',
    value: '1,429',
    change: { value: 8, trend: 'up', period: 'vs last week' },
    icon: 'search',
    color: 'ai-info',
  },
  {
    title: 'Active Users',
    value: '47',
    change: { value: 3, trend: 'up', period: 'vs last month' },
    icon: 'users',
    color: 'ai-success',
  },
];

const mockRecentActivity = [
  {
    id: 1,
    type: 'document_upload',
    title: 'New documents uploaded',
    description: '15 files processed successfully',
    timestamp: '2 minutes ago',
    user: 'Sarah Chen',
    status: 'completed',
  },
  {
    id: 2,
    type: 'search_query',
    title: 'Advanced search performed',
    description: 'Query: "AI implementation strategies"',
    timestamp: '5 minutes ago',
    user: 'Mike Johnson',
    status: 'completed',
  },
  {
    id: 3,
    type: 'user_created',
    title: 'New user account created',
    description: 'alex.rodriguez@company.com',
    timestamp: '1 hour ago',
    user: 'Admin',
    status: 'completed',
  },
  {
    id: 4,
    type: 'document_processing',
    title: 'Batch processing started',
    description: '42 documents in queue',
    timestamp: '2 hours ago',
    user: 'System',
    status: 'in_progress',
  },
];

const iconMap = {
  document: DocumentTextIcon,
  upload: CloudArrowUpIcon,
  search: MagnifyingGlassIcon,
  chart: ChartBarIcon,
  users: UsersIcon,
  cpu: CpuChipIcon,
  clock: ClockIcon,
};

interface MetricCardProps {
  metric: MetricCard;
}

function MetricCardComponent({ metric }: MetricCardProps) {
  const IconComponent = iconMap[metric.icon as keyof typeof iconMap] || DocumentTextIcon;
  const TrendIcon = metric.change?.trend === 'up' ? ArrowUpIcon : ArrowDownIcon;
  
  return (
    <div className="bg-surface rounded-lg border border-border p-6 hover:shadow-1 transition-shadow duration-normal">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <div className={`p-2 rounded-lg bg-${metric.color}/10`}>
            <IconComponent className={`h-6 w-6 text-${metric.color}`} />
          </div>
        </div>
        {metric.change && (
          <div className={`flex items-center text-sm ${
            metric.change.trend === 'up' ? 'text-ai-success' : 'text-ai-danger'
          }`}>
            <TrendIcon className="h-4 w-4 mr-1" />
            {metric.change.value}%
          </div>
        )}
      </div>
      
      <div className="mt-4">
        <h3 className="text-2xl font-bold text-text">{metric.value}</h3>
        <p className="text-sm text-muted mt-1">{metric.title}</p>
        {metric.change && (
          <p className="text-xs text-muted-2 mt-1">{metric.change.period}</p>
        )}
      </div>
    </div>
  );
}

interface ActivityItemProps {
  activity: typeof mockRecentActivity[0];
}

function ActivityItem({ activity }: ActivityItemProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-ai-success bg-ai-success/10';
      case 'in_progress': return 'text-ai-info bg-ai-info/10';
      case 'failed': return 'text-ai-danger bg-ai-danger/10';
      default: return 'text-muted bg-surface-2';
    }
  };

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'document_upload': return CloudArrowUpIcon;
      case 'search_query': return MagnifyingGlassIcon;
      case 'user_created': return UsersIcon;
      case 'document_processing': return CpuChipIcon;
      default: return DocumentTextIcon;
    }
  };

  const IconComponent = getActivityIcon(activity.type);

  return (
    <div className="flex items-start space-x-3 p-4 hover:bg-surface-2 rounded-lg transition-colors duration-fast">
      <div className="flex-shrink-0">
        <div className="w-8 h-8 bg-brand/10 rounded-lg flex items-center justify-center">
          <IconComponent className="h-4 w-4 text-brand" />
        </div>
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium text-text truncate">
            {activity.title}
          </h4>
          <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(activity.status)}`}>
            {activity.status.replace('_', ' ')}
          </span>
        </div>
        
        <p className="text-sm text-muted mt-1">{activity.description}</p>
        
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-muted-2">{activity.user}</span>
          <span className="text-xs text-muted-2">{activity.timestamp}</span>
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { user, hasPermission } = useAuth();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate loading
    const timer = setTimeout(() => setIsLoading(false), 1000);
    return () => clearTimeout(timer);
  }, []);

  const quickActions = [
    {
      title: 'Upload Documents',
      description: 'Add new documents to the system',
      icon: CloudArrowUpIcon,
      path: '/documents/upload',
      permission: 'documents:upload',
      color: 'brand',
    },
    {
      title: 'Search Documents',
      description: 'Find information across all documents',
      icon: MagnifyingGlassIcon,
      path: '/search',
      permission: 'search:execute',
      color: 'ai-info',
    },
    {
      title: 'View Analytics',
      description: 'Analyze document processing metrics',
      icon: ChartBarIcon,
      path: '/analytics',
      permission: 'documents:read',
      color: 'ai-purple',
    },
    {
      title: 'Manage Users',
      description: 'Add and manage user accounts',
      icon: UsersIcon,
      path: '/admin/users',
      permission: 'users:read',
      color: 'ai-success',
    },
  ];

  if (isLoading) {
    return (
      <DashboardLayout title="Dashboard" subtitle="Welcome back to your AI Enablement Platform">
        <div className="space-y-6">
          {/* Loading skeleton */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-surface rounded-lg border border-border p-6 animate-pulse">
                <div className="h-4 bg-surface-2 rounded w-3/4 mb-4"></div>
                <div className="h-8 bg-surface-2 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout 
      title="Dashboard" 
      subtitle={`Welcome back, ${user?.first_name || user?.full_name}! Here's what's happening with your AI platform.`}
    >
      <div className="space-y-8">
        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {mockMetrics.map((metric, index) => (
            <MetricCardComponent key={index} metric={metric} />
          ))}
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Quick Actions */}
          <div className="lg:col-span-1">
            <div className="bg-surface rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-text mb-4">Quick Actions</h3>
              <div className="space-y-3">
                {quickActions
                  .filter(action => hasPermission(action.permission))
                  .map((action, index) => (
                    <Link
                      key={index}
                      to={action.path}
                      className="flex items-center p-3 rounded-lg hover:bg-surface-2 transition-colors duration-fast group"
                    >
                      <div className={`p-2 rounded-lg bg-${action.color}/10 group-hover:bg-${action.color}/20 transition-colors duration-fast`}>
                        <action.icon className={`h-5 w-5 text-${action.color}`} />
                      </div>
                      <div className="ml-3 flex-1">
                        <h4 className="text-sm font-medium text-text group-hover:text-brand transition-colors duration-fast">
                          {action.title}
                        </h4>
                        <p className="text-xs text-muted-2">{action.description}</p>
                      </div>
                    </Link>
                  ))}
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="lg:col-span-2">
            <div className="bg-surface rounded-lg border border-border p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-text">Recent Activity</h3>
                <Link
                  to="/admin/system/logs"
                  className="text-sm text-brand hover:text-brand-strong transition-colors duration-fast"
                >
                  View all
                </Link>
              </div>
              
              <div className="space-y-1">
                {mockRecentActivity.map((activity) => (
                  <ActivityItem key={activity.id} activity={activity} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default DashboardPage;
