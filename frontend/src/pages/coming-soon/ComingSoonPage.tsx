/**
 * ComingSoonPage - Placeholder for apps in active customer development
 * 
 * Displays a professional dashboard with placeholder metrics and a modal
 * indicating the solution is in active development at a customer site.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../../components/layout/Layout';
import {
  Card,
  CardContent,
  Button,
  PageContent,
} from '../../components/ui';
import {
  XMarkIcon,
  ArrowLeftIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  UserGroupIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
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

/* ============================================
   App Configuration - metrics & content per app
   ============================================ */

interface AppConfig {
  title: string;
  subtitle: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
  borderColor: string;
  customerContext: string;
  metrics: {
    label: string;
    value: string;
    change: string;
    trend: 'up' | 'down' | 'neutral';
  }[];
  recentActivity: {
    label: string;
    status: 'completed' | 'in-progress' | 'warning';
    time: string;
  }[];
  capabilities: string[];
}

const appConfigs: Record<string, AppConfig> = {
  'deal-intelligence': {
    title: 'Deal Intelligence',
    subtitle: 'Revenue & Pipeline Analytics',
    description: 'AI-powered pipeline risk scoring, win/loss analysis, and competitive positioning on every deal.',
    icon: CurrencyDollarIcon,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    borderColor: 'border-amber-200 dark:border-amber-800',
    customerContext: 'currently being deployed with a B2B SaaS customer to analyze $47M in pipeline across 230+ active opportunities',
    metrics: [
      { label: 'Pipeline Value', value: '$47.2M', change: '+12.3%', trend: 'up' },
      { label: 'Win Rate', value: '34.8%', change: '+5.2%', trend: 'up' },
      { label: 'Avg Deal Cycle', value: '68 days', change: '-8 days', trend: 'up' },
      { label: 'At-Risk Deals', value: '23', change: '+3', trend: 'down' },
    ],
    recentActivity: [
      { label: 'Enterprise deal risk score updated — Acme Corp flagged as at-risk', status: 'warning', time: '2h ago' },
      { label: 'Win/loss analysis completed for Q4 2025 cohort', status: 'completed', time: '5h ago' },
      { label: 'Competitive intelligence refresh running for 12 accounts', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Pipeline Risk Scoring', 'Win/Loss Analysis', 'Competitive Positioning', 'Deal Velocity Tracking', 'Revenue Forecasting'],
  },
  'rfp-responder': {
    title: 'RFP Responder',
    subtitle: 'Automated Proposal Generation',
    description: 'Auto-draft RFP/RFI responses pulling from past wins, case studies, and product documentation.',
    icon: DocumentCheckIcon,
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50 dark:bg-indigo-900/20',
    borderColor: 'border-indigo-200 dark:border-indigo-800',
    customerContext: 'currently being deployed with a professional services firm to automate response generation across 15+ active RFPs per quarter',
    metrics: [
      { label: 'RFPs In Progress', value: '8', change: '+2', trend: 'neutral' },
      { label: 'Avg Response Time', value: '3.2 days', change: '-4.1 days', trend: 'up' },
      { label: 'Content Reuse Rate', value: '73%', change: '+18%', trend: 'up' },
      { label: 'Win Rate (Assisted)', value: '41%', change: '+9%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Draft generated for Federal Healthcare IT RFP — 47 questions answered', status: 'completed', time: '3h ago' },
      { label: 'Knowledge base updated with 23 new case studies from Q4', status: 'completed', time: '1d ago' },
      { label: 'Compliance section auto-fill running for DoD RFP', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Auto-Draft Generation', 'Past Win Mining', 'Compliance Auto-Fill', 'Case Study Matching', 'Multi-Reviewer Workflow'],
  },
  'customer-health': {
    title: 'Customer Health Monitor',
    subtitle: 'Retention & Expansion Intelligence',
    description: 'Churn prediction, sentiment trends, and expansion signals from support tickets and usage data.',
    icon: HeartIcon,
    color: 'text-rose-600',
    bgColor: 'bg-rose-50 dark:bg-rose-900/20',
    borderColor: 'border-rose-200 dark:border-rose-800',
    customerContext: 'currently being deployed with a SaaS platform to monitor health scores across 1,200+ enterprise accounts',
    metrics: [
      { label: 'Healthy Accounts', value: '847', change: '+23', trend: 'up' },
      { label: 'At-Risk Accounts', value: '38', change: '-7', trend: 'up' },
      { label: 'NPS Score', value: '72', change: '+4', trend: 'up' },
      { label: 'Expansion Revenue', value: '$2.1M', change: '+18%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Churn risk alert — 3 enterprise accounts showing declining engagement', status: 'warning', time: '1h ago' },
      { label: 'Expansion signal detected — Globex Corp usage up 340% this month', status: 'completed', time: '4h ago' },
      { label: 'Sentiment analysis processing 2,847 support tickets from last 30 days', status: 'in-progress', time: '6h ago' },
    ],
    capabilities: ['Health Score Modeling', 'Churn Prediction', 'Sentiment Analysis', 'Expansion Signal Detection', 'CSM Action Recommendations'],
  },
  'ma-analyst': {
    title: 'M&A Analyst',
    subtitle: 'Due Diligence & Target Analysis',
    description: 'Target company profiling, financial health scoring, cultural fit assessment, and risk flags.',
    icon: BuildingOffice2Icon,
    color: 'text-slate-600',
    bgColor: 'bg-slate-50 dark:bg-slate-900/20',
    borderColor: 'border-slate-200 dark:border-slate-700',
    customerContext: 'currently being deployed with a private equity firm to evaluate acquisition targets across a portfolio of 40+ companies',
    metrics: [
      { label: 'Targets Evaluated', value: '42', change: '+6', trend: 'neutral' },
      { label: 'Avg Diligence Time', value: '12 days', change: '-18 days', trend: 'up' },
      { label: 'Risk Flags Found', value: '127', change: 'across 42 targets', trend: 'neutral' },
      { label: 'Cultural Fit Score', value: '7.4/10', change: 'avg', trend: 'neutral' },
    ],
    recentActivity: [
      { label: 'Financial health assessment completed for Initech Corp — 3 risk flags', status: 'warning', time: '2h ago' },
      { label: 'Cultural fit analysis generated for NovaTech acquisition', status: 'completed', time: '8h ago' },
      { label: 'Regulatory risk scan running across 5 new targets', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Target Profiling', 'Financial Health Scoring', 'Cultural Fit Assessment', 'Regulatory Risk Scanning', 'Integration Planning'],
  },
  'spend-optimizer': {
    title: 'Spend Optimizer',
    subtitle: 'Procurement & Cost Intelligence',
    description: 'Procurement spend analysis, vendor consolidation recommendations, and contract renewal alerts.',
    icon: BanknotesIcon,
    color: 'text-emerald-600',
    bgColor: 'bg-emerald-50 dark:bg-emerald-900/20',
    borderColor: 'border-emerald-200 dark:border-emerald-800',
    customerContext: 'currently being deployed with a mid-market enterprise to analyze $120M in annual procurement spend across 800+ vendors',
    metrics: [
      { label: 'Total Spend Analyzed', value: '$120M', change: 'annual', trend: 'neutral' },
      { label: 'Savings Identified', value: '$8.7M', change: '+$2.1M', trend: 'up' },
      { label: 'Vendor Consolidation', value: '47 → 31', change: '-34%', trend: 'up' },
      { label: 'Renewals This Quarter', value: '18', change: '6 urgent', trend: 'down' },
    ],
    recentActivity: [
      { label: 'Contract renewal alert — AWS agreement expires in 45 days, $3.2M at stake', status: 'warning', time: '30m ago' },
      { label: 'Vendor consolidation analysis completed — SaaS tools category', status: 'completed', time: '3h ago' },
      { label: 'Spend anomaly detected — Marketing services up 280% vs last quarter', status: 'warning', time: '1d ago' },
    ],
    capabilities: ['Spend Categorization', 'Vendor Consolidation', 'Contract Renewal Alerts', 'Savings Identification', 'Anomaly Detection'],
  },
  'regulatory-radar': {
    title: 'Regulatory Radar',
    subtitle: 'Compliance & Risk Monitoring',
    description: 'Monitors regulatory changes across jurisdictions, flags impact to your business, and drafts policy updates.',
    icon: ShieldExclamationIcon,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50 dark:bg-orange-900/20',
    borderColor: 'border-orange-200 dark:border-orange-800',
    customerContext: 'currently being deployed with a financial services firm to monitor regulatory changes across 12 jurisdictions and 340+ compliance requirements',
    metrics: [
      { label: 'Regulations Tracked', value: '340+', change: '+28 this month', trend: 'neutral' },
      { label: 'Policy Gaps', value: '12', change: '-5', trend: 'up' },
      { label: 'Jurisdictions', value: '12', change: '+2', trend: 'neutral' },
      { label: 'Compliance Score', value: '94.2%', change: '+1.8%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'New SEC guidance on AI disclosure — impact assessment generated', status: 'warning', time: '4h ago' },
      { label: 'EU AI Act compliance gap analysis completed — 3 action items', status: 'completed', time: '1d ago' },
      { label: 'State privacy law tracker updated — 2 new bills flagged', status: 'in-progress', time: '2d ago' },
    ],
    capabilities: ['Regulatory Change Monitoring', 'Impact Assessment', 'Policy Gap Analysis', 'Compliance Scoring', 'Auto-Draft Policy Updates'],
  },
  'onboarding-copilot': {
    title: 'Onboarding Copilot',
    subtitle: 'Employee Ramp & Knowledge Transfer',
    description: 'Personalized 30/60/90 day plans, auto-assigned training, and answers new hire questions from company knowledge.',
    icon: AcademicCapIcon,
    color: 'text-cyan-600',
    bgColor: 'bg-cyan-50 dark:bg-cyan-900/20',
    borderColor: 'border-cyan-200 dark:border-cyan-800',
    customerContext: 'currently being deployed with a technology company to reduce time-to-productivity for 200+ new hires per year',
    metrics: [
      { label: 'Active Onboardees', value: '34', change: '+12 this month', trend: 'neutral' },
      { label: 'Avg Ramp Time', value: '42 days', change: '-23 days', trend: 'up' },
      { label: 'Knowledge Questions', value: '1,247', change: '+340 this month', trend: 'neutral' },
      { label: 'Satisfaction Score', value: '4.7/5', change: '+0.4', trend: 'up' },
    ],
    recentActivity: [
      { label: '30-day checkpoint completed for Engineering cohort — 12 new hires on track', status: 'completed', time: '2h ago' },
      { label: 'Training path auto-generated for 8 new Sales hires starting Monday', status: 'completed', time: '5h ago' },
      { label: 'Knowledge gap detected — 3 new hires struggling with deployment process docs', status: 'warning', time: '1d ago' },
    ],
    capabilities: ['30/60/90 Day Plans', 'Auto-Assigned Training', 'Knowledge Q&A', 'Progress Tracking', 'Manager Dashboards'],
  },
  'competitive-intel': {
    title: 'Competitive Intel',
    subtitle: 'Market & Competitor Analysis',
    description: 'Real-time competitor monitoring, battle card generation, market positioning, and win/loss pattern analysis.',
    icon: EyeIcon,
    color: 'text-violet-600',
    bgColor: 'bg-violet-50 dark:bg-violet-900/20',
    borderColor: 'border-violet-200 dark:border-violet-800',
    customerContext: 'currently being deployed with a B2B software company to track 24 competitors across product launches, pricing changes, and hiring signals',
    metrics: [
      { label: 'Competitors Tracked', value: '24', change: '+3 this quarter', trend: 'neutral' },
      { label: 'Intel Alerts (30d)', value: '147', change: '+32%', trend: 'up' },
      { label: 'Battle Cards', value: '18', change: '6 updated this week', trend: 'neutral' },
      { label: 'Win Rate vs Top 3', value: '62%', change: '+8%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Competitor pricing change detected — Acme lowered enterprise tier by 20%', status: 'warning', time: '1h ago' },
      { label: 'Battle card auto-updated for NovaTech after their product launch', status: 'completed', time: '4h ago' },
      { label: 'Hiring signal detected — competitor opening 15 AI engineering roles', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Competitor Monitoring', 'Battle Card Generation', 'Pricing Intelligence', 'Hiring Signal Detection', 'Win/Loss Patterns'],
  },
  'campaign-optimizer': {
    title: 'Campaign Optimizer',
    subtitle: 'Marketing Performance & Targeting',
    description: 'Campaign performance analysis, audience segmentation, content recommendations, and channel optimization.',
    icon: MegaphoneIcon,
    color: 'text-pink-600',
    bgColor: 'bg-pink-50 dark:bg-pink-900/20',
    borderColor: 'border-pink-200 dark:border-pink-800',
    customerContext: 'currently being deployed with a DTC brand to optimize $4.2M in quarterly ad spend across 8 channels and 340+ campaigns',
    metrics: [
      { label: 'Active Campaigns', value: '47', change: '+8', trend: 'neutral' },
      { label: 'Avg ROAS', value: '4.2x', change: '+0.8x', trend: 'up' },
      { label: 'CAC', value: '$42', change: '-$13', trend: 'up' },
      { label: 'Conversion Rate', value: '3.8%', change: '+0.9%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Budget reallocation recommended — shift $40K from display to paid social', status: 'warning', time: '2h ago' },
      { label: 'A/B test winner identified — variant B outperforming by 34% on CTR', status: 'completed', time: '6h ago' },
      { label: 'Audience segment analysis running across 1.2M customer profiles', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Campaign Analytics', 'Budget Optimization', 'Audience Segmentation', 'A/B Test Analysis', 'Channel Attribution'],
  },
  'contract-hub': {
    title: 'Contract Hub',
    subtitle: 'Full Lifecycle Contract Management',
    description: 'AI-powered contract drafting, risk analysis, obligation tracking, renewal management, and negotiation benchmarking.',
    icon: DocumentDuplicateIcon,
    color: 'text-teal-600',
    bgColor: 'bg-teal-50 dark:bg-teal-900/20',
    borderColor: 'border-teal-200 dark:border-teal-800',
    customerContext: 'currently being deployed with a professional services firm to manage 2,400+ active contracts across 180 clients',
    metrics: [
      { label: 'Active Contracts', value: '2,412', change: '+87 this quarter', trend: 'neutral' },
      { label: 'Renewal Pipeline', value: '$18.4M', change: '42 renewals in 90 days', trend: 'neutral' },
      { label: 'Risk Clauses Found', value: '234', change: 'across 89 contracts', trend: 'down' },
      { label: 'Avg Draft Time', value: '2.1 hrs', change: '-6.4 hrs', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Auto-renewal deadline in 14 days — Globex Corp master agreement ($2.1M)', status: 'warning', time: '1h ago' },
      { label: 'Risk analysis completed for vendor MSA — 4 non-standard liability clauses flagged', status: 'completed', time: '3h ago' },
      { label: 'Contract draft generated from template — SaaS subscription for new client', status: 'in-progress', time: '5h ago' },
    ],
    capabilities: ['Contract Drafting', 'Risk Analysis', 'Obligation Tracking', 'Renewal Management', 'Negotiation Benchmarking'],
  },
  'it-service-desk': {
    title: 'IT Service Desk AI',
    subtitle: 'Intelligent Ticket Resolution',
    description: 'Auto-triage IT tickets, knowledge base resolution recommendations, SLA prediction, and self-service automation.',
    icon: WrenchScrewdriverIcon,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    borderColor: 'border-blue-200 dark:border-blue-800',
    customerContext: 'currently being deployed with a 5,000-employee enterprise to handle 3,200+ IT tickets per month with AI-assisted resolution',
    metrics: [
      { label: 'Tickets (30d)', value: '3,247', change: '-12% from automation', trend: 'up' },
      { label: 'Auto-Resolved', value: '41%', change: '+14%', trend: 'up' },
      { label: 'Avg Resolution', value: '2.4 hrs', change: '-4.1 hrs', trend: 'up' },
      { label: 'SLA Compliance', value: '97.2%', change: '+3.8%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'VPN connectivity issue auto-resolved for 23 users via self-service runbook', status: 'completed', time: '30m ago' },
      { label: 'P1 incident pattern detected — 8 related tickets in last hour, escalated', status: 'warning', time: '2h ago' },
      { label: 'Knowledge base updated with 12 new resolution articles from closed tickets', status: 'completed', time: '6h ago' },
    ],
    capabilities: ['Auto-Triage', 'Self-Service Resolution', 'SLA Prediction', 'Pattern Detection', 'Knowledge Base Learning'],
  },
  'supply-chain': {
    title: 'Supply Chain Monitor',
    subtitle: 'Logistics & Supplier Intelligence',
    description: 'Disruption alerts, supplier risk scoring, logistics optimization, and demand forecasting.',
    icon: TruckIcon,
    color: 'text-amber-700',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    borderColor: 'border-amber-200 dark:border-amber-800',
    customerContext: 'currently being deployed with a manufacturing company to monitor 340 suppliers across 12 countries with real-time disruption tracking',
    metrics: [
      { label: 'Suppliers Monitored', value: '340', change: 'across 12 countries', trend: 'neutral' },
      { label: 'Active Disruptions', value: '7', change: '-3 from last week', trend: 'up' },
      { label: 'On-Time Delivery', value: '94.1%', change: '+2.3%', trend: 'up' },
      { label: 'Cost Avoidance', value: '$3.2M', change: 'YTD', trend: 'neutral' },
    ],
    recentActivity: [
      { label: 'Port congestion alert — Shanghai delays impacting 4 active POs', status: 'warning', time: '45m ago' },
      { label: 'Alternative supplier identified for critical component — 30% shorter lead time', status: 'completed', time: '4h ago' },
      { label: 'Demand forecast updated — Q3 projections adjusted based on order trends', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Disruption Alerts', 'Supplier Risk Scoring', 'Logistics Optimization', 'Demand Forecasting', 'Alternative Sourcing'],
  },
  'product-insights': {
    title: 'Product Insights',
    subtitle: 'Feature Analytics & User Feedback',
    description: 'Feature usage analytics, user feedback synthesis, prioritization signals, and adoption tracking.',
    icon: LightBulbIcon,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50 dark:bg-yellow-900/20',
    borderColor: 'border-yellow-200 dark:border-yellow-800',
    customerContext: 'currently being deployed with a SaaS product team to synthesize feedback from 12,000+ users across support tickets, NPS surveys, and in-app signals',
    metrics: [
      { label: 'Feature Requests', value: '1,847', change: '+230 this month', trend: 'neutral' },
      { label: 'Top Request Theme', value: 'API access', change: '342 mentions', trend: 'neutral' },
      { label: 'Feature Adoption', value: '67%', change: '+4% avg', trend: 'up' },
      { label: 'User Satisfaction', value: '4.3/5', change: '+0.2', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Feedback cluster identified — 89 users requesting bulk export in last 2 weeks', status: 'completed', time: '1h ago' },
      { label: 'Adoption drop detected — new dashboard feature at 23% after 30 days', status: 'warning', time: '3h ago' },
      { label: 'Sentiment analysis processing 2,400 NPS comments from Q4 survey', status: 'in-progress', time: '8h ago' },
    ],
    capabilities: ['Usage Analytics', 'Feedback Synthesis', 'Prioritization Signals', 'Adoption Tracking', 'Sentiment Analysis'],
  },
  'eliza-engage': {
    title: 'Eliza Engage',
    subtitle: 'Social Media Intelligence & Response',
    description: 'Real-time social media monitoring, sentiment analysis, automated alerts, and response management across Twitter and other platforms.',
    icon: ChatBubbleOvalLeftEllipsisIcon,
    color: 'text-sky-600',
    bgColor: 'bg-sky-50 dark:bg-sky-900/20',
    borderColor: 'border-sky-200 dark:border-sky-800',
    customerContext: 'currently being deployed with an airline to monitor 50K+ daily tweets, detect service disruptions, and coordinate real-time customer response',
    metrics: [
      { label: 'Tweets Tracked (24h)', value: '52,847', change: '+18% vs avg', trend: 'neutral' },
      { label: 'Sentiment Score', value: '72%', change: '+3%', trend: 'up' },
      { label: 'Avg Response Time', value: '8 min', change: '-22 min', trend: 'up' },
      { label: 'Active Alerts', value: '4', change: '-2 from yesterday', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Sentiment spike detected — negative tweets up 340% around JFK delays', status: 'warning', time: '15m ago' },
      { label: 'Auto-response templates deployed for weather-related flight cancellations', status: 'completed', time: '1h ago' },
      { label: 'Influencer mention detected — travel blogger with 240K followers praised new lounge', status: 'completed', time: '3h ago' },
    ],
    capabilities: ['Real-Time Monitoring', 'Sentiment Analysis', 'Alert Management', 'Response Templates', 'Influencer Detection'],
  },
  'incident-commander': {
    title: 'Incident Commander',
    subtitle: 'Incident Response & Root Cause Analysis',
    description: 'Incident response coordination, root cause analysis, post-mortem generation, and prevention recommendations.',
    icon: FireIcon,
    color: 'text-red-600',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    borderColor: 'border-red-200 dark:border-red-800',
    customerContext: 'currently being deployed with a cloud infrastructure company to reduce MTTR across 400+ production services handling 2M+ requests/sec',
    metrics: [
      { label: 'MTTR', value: '18 min', change: '-34 min', trend: 'up' },
      { label: 'Incidents (30d)', value: '12', change: '-8', trend: 'up' },
      { label: 'Auto-Diagnosed', value: '67%', change: '+23%', trend: 'up' },
      { label: 'Recurring Prevention', value: '89%', change: '+12%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'P1 auto-diagnosed — database connection pool exhaustion, runbook triggered', status: 'completed', time: '2h ago' },
      { label: 'Post-mortem auto-generated for yesterday\'s API latency spike', status: 'completed', time: '6h ago' },
      { label: 'Pattern match — current alert correlates with 3 previous incidents, fix suggested', status: 'warning', time: '1d ago' },
    ],
    capabilities: ['Auto-Diagnosis', 'Root Cause Analysis', 'Post-Mortem Generation', 'Runbook Automation', 'Pattern Detection'],
  },
  'partner-intelligence': {
    title: 'Partner Intelligence',
    subtitle: 'Channel & Partner Analytics',
    description: 'Partner performance analytics, co-sell opportunity detection, enablement tracking, and channel optimization.',
    icon: LinkIcon,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50 dark:bg-purple-900/20',
    borderColor: 'border-purple-200 dark:border-purple-800',
    customerContext: 'currently being deployed with a technology vendor to optimize a 120-partner ecosystem generating $85M in annual channel revenue',
    metrics: [
      { label: 'Active Partners', value: '120', change: '+14 this quarter', trend: 'neutral' },
      { label: 'Channel Revenue', value: '$85M', change: '+22%', trend: 'up' },
      { label: 'Co-Sell Pipeline', value: '$12.4M', change: '+$3.1M', trend: 'up' },
      { label: 'Certification Rate', value: '78%', change: '+11%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Co-sell opportunity detected — partner overlap with 3 enterprise prospects', status: 'completed', time: '2h ago' },
      { label: 'Partner tier upgrade triggered — CloudFirst exceeded Gold threshold', status: 'completed', time: '5h ago' },
      { label: 'Enablement gap identified — 12 partners haven\'t completed new product training', status: 'warning', time: '1d ago' },
    ],
    capabilities: ['Partner Performance', 'Co-Sell Detection', 'Enablement Tracking', 'Tier Management', 'Revenue Attribution'],
  },
  'board-report-generator': {
    title: 'Board Report Generator',
    subtitle: 'Executive Reporting & KPI Dashboards',
    description: 'Auto-generate quarterly board decks from live cross-functional data with executive summaries and trend analysis.',
    icon: PresentationChartBarIcon,
    color: 'text-gray-700',
    bgColor: 'bg-gray-50 dark:bg-gray-800/40',
    borderColor: 'border-gray-200 dark:border-gray-700',
    customerContext: 'currently being deployed with a growth-stage company to automate quarterly board reporting across finance, product, sales, and engineering',
    metrics: [
      { label: 'Data Sources', value: '14', change: 'connected', trend: 'neutral' },
      { label: 'Report Gen Time', value: '4 min', change: '-3.5 days', trend: 'up' },
      { label: 'KPIs Tracked', value: '87', change: 'across 6 departments', trend: 'neutral' },
      { label: 'Reports Generated', value: '24', change: '+6 this quarter', trend: 'neutral' },
    ],
    recentActivity: [
      { label: 'Q4 board deck auto-generated — 42 slides with executive summaries', status: 'completed', time: '1d ago' },
      { label: 'Revenue variance narrative generated — flagged 3 metrics outside threshold', status: 'warning', time: '2d ago' },
      { label: 'New data source connected — engineering velocity metrics from Jira', status: 'completed', time: '3d ago' },
    ],
    capabilities: ['Auto-Generated Decks', 'Cross-Functional KPIs', 'Trend Narratives', 'Variance Alerts', 'Historical Benchmarks'],
  },
  'knowledge-miner': {
    title: 'Knowledge Miner',
    subtitle: 'Institutional Knowledge & Expertise Mapping',
    description: 'Captures and surfaces tribal knowledge from departing employees, old Slack threads, meeting notes, and scattered documentation.',
    icon: CircleStackIcon,
    color: 'text-indigo-700',
    bgColor: 'bg-indigo-50 dark:bg-indigo-900/20',
    borderColor: 'border-indigo-200 dark:border-indigo-800',
    customerContext: 'currently being deployed with a consulting firm to capture and preserve institutional knowledge across 800+ consultants and 50K+ project artifacts',
    metrics: [
      { label: 'Knowledge Articles', value: '12,847', change: '+1,240 auto-generated', trend: 'up' },
      { label: 'Sources Indexed', value: '8', change: 'Slack, Confluence, Drive, etc.', trend: 'neutral' },
      { label: 'Expert Maps', value: '340', change: 'people mapped to topics', trend: 'neutral' },
      { label: 'Search Success', value: '91%', change: '+18%', trend: 'up' },
    ],
    recentActivity: [
      { label: 'Departing employee knowledge captured — 47 critical processes documented from exit interview', status: 'completed', time: '3h ago' },
      { label: 'Knowledge gap detected — no documentation exists for client billing reconciliation process', status: 'warning', time: '8h ago' },
      { label: 'Expert map updated — 12 new topic-expert associations from Slack activity', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Auto-Documentation', 'Expertise Mapping', 'Knowledge Gap Detection', 'Exit Knowledge Capture', 'Cross-Source Search'],
  },
  'brand-guardian': {
    title: 'Brand Guardian',
    subtitle: 'Brand Consistency & Content Compliance',
    description: 'Brand consistency monitoring, tone analysis, content compliance checking, and style guide enforcement across all channels.',
    icon: ShieldCheckIcon,
    color: 'text-green-700',
    bgColor: 'bg-green-50 dark:bg-green-900/20',
    borderColor: 'border-green-200 dark:border-green-800',
    customerContext: 'currently being deployed with a global consumer brand to enforce brand consistency across 14 markets, 200+ content creators, and 8 channels',
    metrics: [
      { label: 'Content Scanned (30d)', value: '4,281', change: '+840', trend: 'neutral' },
      { label: 'Brand Compliance', value: '94.7%', change: '+6.2%', trend: 'up' },
      { label: 'Tone Violations', value: '23', change: '-41', trend: 'up' },
      { label: 'Markets Covered', value: '14', change: '+2', trend: 'neutral' },
    ],
    recentActivity: [
      { label: 'Off-brand content flagged — social post using deprecated logo in APAC market', status: 'warning', time: '1h ago' },
      { label: 'Style guide compliance report generated for Q4 marketing materials', status: 'completed', time: '4h ago' },
      { label: 'Tone analysis running across 340 new product descriptions for EU launch', status: 'in-progress', time: '1d ago' },
    ],
    capabilities: ['Brand Monitoring', 'Tone Analysis', 'Style Guide Enforcement', 'Content Compliance', 'Multi-Market Coverage'],
  },
};

/* ============================================
   Trend Icon Helper
   ============================================ */

function TrendIndicator({ trend, change }: { trend: 'up' | 'down' | 'neutral'; change: string }) {
  if (trend === 'up') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
        <ArrowTrendingUpIcon className="h-3.5 w-3.5" />
        {change}
      </span>
    );
  }
  if (trend === 'down') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-red-500 dark:text-red-400">
        <ArrowTrendingDownIcon className="h-3.5 w-3.5" />
        {change}
      </span>
    );
  }
  return (
    <span className="text-xs text-gray-500 dark:text-gray-400">{change}</span>
  );
}

/* ============================================
   Status Icon Helper
   ============================================ */

function StatusIcon({ status }: { status: 'completed' | 'in-progress' | 'warning' }) {
  if (status === 'completed') return <CheckCircleIcon className="h-4 w-4 text-emerald-500 flex-shrink-0" />;
  if (status === 'warning') return <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 flex-shrink-0" />;
  return <ClockIcon className="h-4 w-4 text-blue-500 flex-shrink-0" />;
}

/* ============================================
   Modal Component
   ============================================ */

function DevelopmentModal({ config, onClose }: { config: AppConfig; onClose: () => void }) {
  const Icon = config.icon;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="relative w-full max-w-lg bg-white dark:bg-dark-surface rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {/* Colored top bar */}
        <div className={`h-1.5 ${config.bgColor.replace('bg-', 'bg-').replace('/50', '/80').replace('/20', '/60')} bg-gradient-to-r from-eliza-red to-eliza-red/70`} />
        
        <div className="p-8">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:text-gray-300 dark:hover:bg-dark-surface-2 transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>

          {/* Icon + Title */}
          <div className="flex items-center gap-4 mb-6">
            <div className={`p-3 rounded-xl ${config.bgColor} ${config.borderColor} border`}>
              <Icon className={`h-7 w-7 ${config.color}`} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-charcoal dark:text-gray-100">{config.title}</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">{config.subtitle}</p>
            </div>
          </div>

          {/* Message */}
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-1">
                Active Customer Development
              </p>
              <p className="text-sm text-amber-700 dark:text-amber-400 leading-relaxed">
                This solution is <strong>{config.customerContext}</strong>. The data shown here is representative of the solution's capabilities and is not from a live internal demo environment.
              </p>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              {config.description} The metrics and activity displayed are illustrative of the insights this solution provides in production.
            </p>
          </div>

          {/* Action */}
          <div className="mt-6 flex justify-end">
            <Button onClick={onClose}>
              Explore Dashboard
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================
   Main Page Component
   ============================================ */

interface ComingSoonPageProps {
  appId: string;
}

export default function ComingSoonPage({ appId }: ComingSoonPageProps) {
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(true);
  const config = appConfigs[appId];

  if (!config) {
    return (
      <Layout>
        <PageContent>
          <div className="text-center py-20">
            <p className="text-gray-500">App not found.</p>
            <Button onClick={() => navigate('/home')} className="mt-4">Go Home</Button>
          </div>
        </PageContent>
      </Layout>
    );
  }

  const Icon = config.icon;

  return (
    <Layout>
      <PageContent>
        {/* Modal */}
        {showModal && (
          <DevelopmentModal config={config} onClose={() => setShowModal(false)} />
        )}

        {/* Page Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/home')}
            className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-charcoal dark:text-gray-400 dark:hover:text-gray-200 mb-4 transition-colors"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Back to Home
          </button>
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl ${config.bgColor} ${config.borderColor} border`}>
              <Icon className={`h-8 w-8 ${config.color}`} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-charcoal dark:text-gray-100">{config.title}</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">{config.subtitle}</p>
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {config.metrics.map((metric, idx) => (
            <Card key={idx}>
              <CardContent className="p-5">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                  {metric.label}
                </p>
                <p className="text-2xl font-bold text-charcoal dark:text-gray-100 mb-1">
                  {metric.value}
                </p>
                <TrendIndicator trend={metric.trend} change={metric.change} />
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Activity */}
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-6">
                <h3 className="text-sm font-semibold text-charcoal dark:text-gray-100 uppercase tracking-wider mb-4">
                  Recent Activity
                </h3>
                <div className="space-y-4">
                  {config.recentActivity.map((activity, idx) => (
                    <div key={idx} className="flex items-start gap-3">
                      <StatusIcon status={activity.status} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-charcoal dark:text-gray-200 leading-relaxed">
                          {activity.label}
                        </p>
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{activity.time}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Capabilities */}
          <div>
            <Card>
              <CardContent className="p-6">
                <h3 className="text-sm font-semibold text-charcoal dark:text-gray-100 uppercase tracking-wider mb-4">
                  Capabilities
                </h3>
                <div className="space-y-2.5">
                  {config.capabilities.map((cap, idx) => (
                    <div key={idx} className="flex items-center gap-2.5">
                      <CheckCircleIcon className={`h-4 w-4 ${config.color} flex-shrink-0`} />
                      <span className="text-sm text-gray-600 dark:text-gray-300">{cap}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Development badge */}
            <div className={`mt-4 p-4 rounded-xl ${config.bgColor} ${config.borderColor} border`}>
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider mb-1">
                Status
              </p>
              <p className="text-sm font-medium text-charcoal dark:text-gray-200">
                In Active Customer Development
              </p>
              <button
                onClick={() => setShowModal(true)}
                className={`text-xs ${config.color} hover:underline mt-1`}
              >
                View details
              </button>
            </div>
          </div>
        </div>
      </PageContent>
    </Layout>
  );
}
