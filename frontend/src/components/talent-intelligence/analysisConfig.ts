/**
 * Analysis Modal Configuration
 * 
 * Defines the sections, their metadata, and requirements for the analysis modal.
 */

import {
  BuildingOfficeIcon,
  SparklesIcon,
  BuildingLibraryIcon,
  DocumentTextIcon,
  UserGroupIcon,
  UserIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';

export type AnalysisSection =
  | 'analysis-setup'
  | 'ats-connection'
  | 'career-blueprint'
  | 'company-dna'
  | 'job-description'
  | 'candidate-source'
  | 'ideal-candidate';

export interface AnalysisSectionConfig {
  id: AnalysisSection;
  label: string;
  shortLabel: string; // For tight spaces
  icon: React.ComponentType<{ className?: string }>;
  isRequired: boolean;
  infoTooltip: string;
  infoDetail: string;
}

export const ANALYSIS_SECTIONS: AnalysisSectionConfig[] = [
  {
    id: 'analysis-setup',
    label: 'Analysis Setup',
    shortLabel: 'Setup',
    icon: Cog6ToothIcon,
    isRequired: true, // Name is required to save
    infoTooltip: 'Configure analysis name, description, and search limits.',
    infoDetail:
      'Set up the basic details for your analysis including the name, description, and limits for how many candidates to search from the market and your ATS.',
  },
  {
    id: 'ats-connection',
    label: 'ATS Connection',
    shortLabel: 'ATS',
    icon: BuildingOfficeIcon,
    isRequired: false,
    infoTooltip: 'Connect to your ATS to pull jobs and candidates directly.',
    infoDetail:
      'Link your Applicant Tracking System (e.g., Greenhouse, Lever) to import job postings and sync candidate data automatically. This enables the "Select from ATS" options in Job Description and Candidate Source.',
  },
  {
    id: 'career-blueprint',
    label: 'Career Blueprint',
    shortLabel: 'Blueprint',
    icon: SparklesIcon,
    isRequired: false,
    infoTooltip: 'AI-generated career progression paths for the role.',
    infoDetail:
      'Generate a blueprint showing typical career trajectories, skills progression, and role expectations. This helps identify candidates with the right growth potential and career alignment.',
  },
  {
    id: 'company-dna',
    label: 'Company DNA',
    shortLabel: 'DNA',
    icon: BuildingLibraryIcon,
    isRequired: false,
    infoTooltip: "Analyze a company's workforce to find similar candidates.",
    infoDetail:
      "Build a profile of a target company's employees to understand their skills, backgrounds, and experience patterns. Use this to find candidates who would be a cultural and technical fit.",
  },
  {
    id: 'job-description',
    label: 'Job Description',
    shortLabel: 'Job Desc',
    icon: DocumentTextIcon,
    isRequired: true,
    infoTooltip: 'The job posting or role requirements to match against.',
    infoDetail:
      'Provide the job description, requirements, and qualifications. This is the primary input for candidate matching. You can paste text, upload a PDF, or select from your ATS.',
  },
  {
    id: 'candidate-source',
    label: 'Candidate Source',
    shortLabel: 'Candidates',
    icon: UserGroupIcon,
    isRequired: true,
    infoTooltip: 'Where to search for candidates.',
    infoDetail:
      'Choose where to find candidates: search the external talent market, pull from your ATS pipeline, or both. Set limits to control the search scope and cost.',
  },
  {
    id: 'ideal-candidate',
    label: 'Ideal Candidate',
    shortLabel: 'Ideal',
    icon: UserIcon,
    isRequired: false,
    infoTooltip: 'Describe your ideal hire or provide an example profile.',
    infoDetail:
      'Optionally describe must-haves, nice-to-haves, dealbreakers, and personality traits. You can also provide a LinkedIn profile of someone who represents your ideal candidate.',
  },
];

/**
 * Get section config by ID
 */
export function getSectionConfig(id: AnalysisSection): AnalysisSectionConfig | undefined {
  return ANALYSIS_SECTIONS.find((s) => s.id === id);
}

/**
 * Get all required section IDs
 */
export const REQUIRED_SECTIONS: AnalysisSection[] = ANALYSIS_SECTIONS
  .filter((s) => s.isRequired)
  .map((s) => s.id);

/**
 * Check if all required sections are complete
 */
export function areRequiredSectionsComplete(
  completionState: Record<AnalysisSection, boolean>
): boolean {
  return REQUIRED_SECTIONS.every((id) => completionState[id]);
}
