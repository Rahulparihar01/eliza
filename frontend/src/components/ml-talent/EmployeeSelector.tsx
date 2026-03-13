/**
 * LinkedIn Profile Selector Component
 * 
 * Allows users to:
 * 1. Select an existing Career Blueprint
 * 2. Create a new blueprint by adding LinkedIn profile URLs
 * 
 * Profiles are enriched via Eliza People Search with caching to minimize API calls.
 */

import React, { useState, useEffect } from 'react';
import { 
  CheckCircleIcon, 
  PlusIcon,
  XMarkIcon,
  LinkIcon,
  ArrowPathIcon,
  SparklesIcon,
  UserGroupIcon,
  FingerPrintIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';

interface LinkedInProfile {
  url: string;
  status: 'pending' | 'enriching' | 'enriched' | 'error';
  name?: string;
  title?: string;
  company?: string;
  skills?: string[];
  experience?: number;
  cached?: boolean;
  error?: string;
  enrichedData?: any;  // Full PDL response for blueprint creation
}

interface CareerBlueprint {
  id: number;
  name: string;
  description?: string;
  role_category?: string;
  source_profile_count: number;
  skill_profile?: {
    core_skills?: string[];
  };
  experience_profile?: {
    avg_years?: number;
  };
  usage_count: number;
  is_active: boolean;
}

interface EmployeeSelectorProps {
  linkedInUrls: string[];
  onLinkedInUrlsChange: (urls: string[]) => void;
  onContinue: (linkedInUrls: string[], blueprintId?: number) => void;
}

export function EmployeeSelector({
  linkedInUrls,
  onLinkedInUrlsChange,
  onContinue,
}: EmployeeSelectorProps) {
  // Blueprint selection state
  const [blueprints, setBlueprints] = useState<CareerBlueprint[]>([]);
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<number | null>(null);
  const [isLoadingBlueprints, setIsLoadingBlueprints] = useState(true);
  const [mode, setMode] = useState<'select' | 'create'>('select');
  
  // New blueprint creation state
  const [newBlueprintName, setNewBlueprintName] = useState('');
  const [showNamePrompt, setShowNamePrompt] = useState(false);
  const [isCreatingBlueprint, setIsCreatingBlueprint] = useState(false);
  
  // LinkedIn profile state
  const [newLinkedInUrl, setNewLinkedInUrl] = useState('');
  const [linkedInProfiles, setLinkedInProfiles] = useState<LinkedInProfile[]>([]);
  const [isAddingMultiple, setIsAddingMultiple] = useState(false);
  const [bulkUrls, setBulkUrls] = useState('');

  // Load existing blueprints
  useEffect(() => {
    loadBlueprints();
  }, []);

  const loadBlueprints = async () => {
    setIsLoadingBlueprints(true);
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/talent-config/blueprints');
      setBlueprints(response.data.blueprints || []);
      // If no blueprints exist, default to create mode
      if ((response.data.blueprints || []).length === 0) {
        setMode('create');
      }
    } catch (error) {
      console.error('Failed to load blueprints:', error);
      setMode('create');
    } finally {
      setIsLoadingBlueprints(false);
    }
  };

  // Add LinkedIn URL and enrich
  const handleAddLinkedInUrl = async (urlToAdd?: string) => {
    const url = (urlToAdd || newLinkedInUrl).trim();
    
    if (!url) return;
    
    // Normalize URL
    let normalizedUrl = url;
    if (!url.startsWith('http')) {
      normalizedUrl = 'https://' + url;
    }
    if (!normalizedUrl.includes('linkedin.com')) {
      normalizedUrl = 'https://linkedin.com/in/' + url;
    }
    
    // Check if already added
    if (linkedInProfiles.some(p => p.url === normalizedUrl)) {
      return;
    }

    // Add to profiles list with enriching status
    const newProfile: LinkedInProfile = {
      url: normalizedUrl,
      status: 'enriching',
    };
    
    setLinkedInProfiles(prev => [...prev, newProfile]);
    if (!urlToAdd) setNewLinkedInUrl('');
    
    // Enrich the profile
    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/linkedin/enrich', {
        linkedin_url: normalizedUrl,
      });
      
      if (response.data.found) {
        setLinkedInProfiles(prev => prev.map(p => 
          p.url === normalizedUrl 
            ? {
                ...p,
                status: 'enriched' as const,
                name: response.data.full_name,
                title: response.data.job_title,
                company: response.data.job_company_name,
                skills: response.data.skills?.slice(0, 10) || [],
                experience: response.data.inferred_years_experience,
                cached: response.data.cached || false,
                enrichedData: response.data,  // Store full data for blueprint creation
              }
            : p
        ));
        
        // Add to parent's URL list
        onLinkedInUrlsChange([...linkedInUrls, normalizedUrl]);
      } else {
        setLinkedInProfiles(prev => prev.map(p => 
          p.url === normalizedUrl 
            ? { ...p, status: 'error' as const, error: response.data.error_message || 'Profile not found' }
            : p
        ));
      }
    } catch (error: any) {
      console.error('Failed to enrich LinkedIn profile:', error);
      setLinkedInProfiles(prev => prev.map(p => 
        p.url === normalizedUrl 
          ? { ...p, status: 'error' as const, error: error?.response?.data?.detail || 'Enrichment failed' }
          : p
      ));
    }
  };

  // Handle bulk add
  const handleBulkAdd = async () => {
    const urls = bulkUrls
      .split('\n')
      .map(url => url.trim())
      .filter(url => url.length > 0);
    
    setBulkUrls('');
    setIsAddingMultiple(false);
    
    // Add each URL with a small delay to avoid overwhelming the API
    for (const url of urls) {
      await handleAddLinkedInUrl(url);
    }
  };

  // Remove LinkedIn URL
  const handleRemoveLinkedInUrl = (url: string) => {
    setLinkedInProfiles(prev => prev.filter(p => p.url !== url));
    onLinkedInUrlsChange(linkedInUrls.filter(u => u !== url));
  };

  // Retry enrichment
  const handleRetryEnrichment = async (url: string) => {
    setLinkedInProfiles(prev => prev.map(p => 
      p.url === url ? { ...p, status: 'enriching' as const, error: undefined } : p
    ));
    
    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/linkedin/enrich', {
        linkedin_url: url,
      });
      
      if (response.data.found) {
        setLinkedInProfiles(prev => prev.map(p => 
          p.url === url 
            ? {
                ...p,
                status: 'enriched' as const,
                name: response.data.full_name,
                title: response.data.job_title,
                company: response.data.job_company_name,
                skills: response.data.skills?.slice(0, 10) || [],
                experience: response.data.inferred_years_experience,
                cached: response.data.cached || false,
                enrichedData: response.data,
              }
            : p
        ));
        
        if (!linkedInUrls.includes(url)) {
          onLinkedInUrlsChange([...linkedInUrls, url]);
        }
      } else {
        setLinkedInProfiles(prev => prev.map(p => 
          p.url === url 
            ? { ...p, status: 'error' as const, error: 'Profile not found' }
            : p
        ));
      }
    } catch (error: any) {
      setLinkedInProfiles(prev => prev.map(p => 
        p.url === url 
          ? { ...p, status: 'error' as const, error: error?.response?.data?.detail || 'Enrichment failed' }
          : p
      ));
    }
  };

  // Create a new blueprint from enriched profiles
  const handleCreateBlueprint = async () => {
    if (!newBlueprintName.trim()) return;
    
    const enrichedProfiles = linkedInProfiles
      .filter(p => p.status === 'enriched' && p.enrichedData)
      .map(p => p.enrichedData);
    
    if (enrichedProfiles.length === 0) return;
    
    setIsCreatingBlueprint(true);
    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/talent-config/blueprints', {
        name: newBlueprintName.trim(),
        linkedin_urls: linkedInUrls,
        enriched_profiles: enrichedProfiles,
        role_category: 'engineering',  // Could make this selectable
      });
      
      // Use the newly created blueprint
      setSelectedBlueprintId(response.data.id);
      setShowNamePrompt(false);
      
      // Continue with the new blueprint
      onContinue(linkedInUrls, response.data.id);
    } catch (error: any) {
      console.error('Failed to create blueprint:', error);
      alert(error?.response?.data?.detail || 'Failed to create blueprint');
    } finally {
      setIsCreatingBlueprint(false);
    }
  };

  // Handle continue with existing blueprint
  const handleContinueWithBlueprint = () => {
    if (selectedBlueprintId) {
      const blueprint = blueprints.find(b => b.id === selectedBlueprintId);
      // Pass empty URLs since we're using an existing blueprint
      onContinue([], selectedBlueprintId);
    }
  };

  // Handle continue with new profiles (prompt for blueprint name)
  const handleContinueWithNewProfiles = () => {
    if (enrichedCount > 0) {
      setShowNamePrompt(true);
    }
  };

  const enrichedCount = linkedInProfiles.filter(p => p.status === 'enriched').length;
  const cachedCount = linkedInProfiles.filter(p => p.status === 'enriched' && p.cached).length;
  const canContinueCreate = enrichedCount > 0;
  const canContinueSelect = selectedBlueprintId !== null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-brand/10 mb-4">
          <FingerPrintIcon className="w-8 h-8 text-brand" />
        </div>
        <h2 className="text-2xl font-bold text-text mb-2">Career Blueprint</h2>
        <p className="text-muted max-w-2xl mx-auto">
          Select an existing blueprint or create a new one from LinkedIn profiles of ideal candidates.
        </p>
      </div>

      {/* Mode Selector Tabs */}
      {!isLoadingBlueprints && blueprints.length > 0 && (
        <div className="flex justify-center gap-2 mb-6">
          <button
            onClick={() => setMode('select')}
            className={`px-6 py-2.5 rounded-lg font-medium transition-all flex items-center gap-2 ${
              mode === 'select'
                ? 'bg-brand text-on-brand shadow-lg'
                : 'bg-surface-2 text-muted-2 hover:text-text hover:bg-surface-3'
            }`}
          >
            <DocumentDuplicateIcon className="w-5 h-5" />
            Use Existing Blueprint
          </button>
          <button
            onClick={() => setMode('create')}
            className={`px-6 py-2.5 rounded-lg font-medium transition-all flex items-center gap-2 ${
              mode === 'create'
                ? 'bg-brand text-on-brand shadow-lg'
                : 'bg-surface-2 text-muted-2 hover:text-text hover:bg-surface-3'
            }`}
          >
            <PlusIcon className="w-5 h-5" />
            Create New Blueprint
          </button>
        </div>
      )}

      {/* Loading State */}
      {isLoadingBlueprints && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand border-t-transparent" />
        </div>
      )}

      {/* Select Existing Blueprint */}
      {!isLoadingBlueprints && mode === 'select' && blueprints.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-text">Select a Blueprint</h3>
          <div className="space-y-2">
            {blueprints.map((blueprint) => (
              <button
                key={blueprint.id}
                onClick={() => setSelectedBlueprintId(blueprint.id)}
                className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                  selectedBlueprintId === blueprint.id
                    ? 'border-brand bg-brand/5'
                    : 'border-border bg-surface hover:border-brand/50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <FingerPrintIcon className="w-5 h-5 text-brand" />
                      <h4 className="font-semibold text-text">{blueprint.name}</h4>
                      {blueprint.role_category && (
                        <span className="px-2 py-0.5 text-xs rounded bg-surface-2 text-muted-2 capitalize">
                          {blueprint.role_category}
                        </span>
                      )}
                    </div>
                    {blueprint.description && (
                      <p className="text-sm text-muted-2 mt-1">{blueprint.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-2">
                      <span>{blueprint.source_profile_count} profiles</span>
                      {blueprint.experience_profile?.avg_years && (
                        <span>~{blueprint.experience_profile.avg_years.toFixed(0)}y avg experience</span>
                      )}
                      <span>{blueprint.usage_count} uses</span>
                    </div>
                    {blueprint.skill_profile?.core_skills && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {blueprint.skill_profile.core_skills.slice(0, 5).map((skill) => (
                          <span key={skill} className="px-2 py-0.5 text-xs rounded bg-brand/10 text-brand">
                            {skill}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                    selectedBlueprintId === blueprint.id
                      ? 'border-brand bg-brand'
                      : 'border-muted-2'
                  }`}>
                    {selectedBlueprintId === blueprint.id && (
                      <CheckCircleIcon className="w-4 h-4 text-on-brand" />
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Continue with Selected Blueprint */}
          <div className="flex justify-end pt-4 border-t border-border">
            <button
              onClick={handleContinueWithBlueprint}
              disabled={!canContinueSelect}
              className={`px-8 py-3 rounded-lg font-medium transition-colors text-lg ${
                canContinueSelect
                  ? 'bg-brand text-on-brand hover:bg-brand-strong'
                  : 'bg-surface-2 text-muted-2 cursor-not-allowed'
              }`}
            >
              Continue with Blueprint →
            </button>
          </div>
        </div>
      )}

      {/* Create New Blueprint Mode */}
      {!isLoadingBlueprints && mode === 'create' && (
        <>
          {/* Instructions */}
          <div className="bg-info/10 border border-info/30 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <SparklesIcon className="w-5 h-5 text-info flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-text mb-1">Create a New Blueprint</p>
                <p className="text-muted">
                  Add LinkedIn profiles of your best employees or ideal candidates. 
                  We'll analyze their backgrounds and save this as a reusable blueprint.
                </p>
              </div>
            </div>
          </div>

      {/* Add LinkedIn URL Input */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text">Add LinkedIn Profiles</h3>
          <button
            onClick={() => setIsAddingMultiple(!isAddingMultiple)}
            className="text-sm text-brand hover:text-brand-strong transition-colors"
          >
            {isAddingMultiple ? 'Single URL' : 'Add Multiple'}
          </button>
        </div>

        {isAddingMultiple ? (
          <div className="space-y-3">
            <textarea
              placeholder="Paste multiple LinkedIn URLs (one per line)&#10;https://linkedin.com/in/johndoe&#10;https://linkedin.com/in/janesmith"
              value={bulkUrls}
              onChange={(e) => setBulkUrls(e.target.value)}
              rows={5}
              className="w-full px-4 py-3 bg-surface-2 border border-border rounded-lg text-text placeholder-muted-2 focus:outline-none focus:ring-2 focus:ring-brand resize-none font-mono text-sm"
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setIsAddingMultiple(false);
                  setBulkUrls('');
                }}
                className="px-4 py-2 text-muted-2 hover:text-text transition-colors"
              >
                Cancel
              </button>
                  <button
                onClick={handleBulkAdd}
                disabled={!bulkUrls.trim()}
                className={`px-6 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
                  bulkUrls.trim()
                    ? 'bg-brand text-on-brand hover:bg-brand-strong'
                    : 'bg-surface-2 text-muted-2 cursor-not-allowed'
                }`}
              >
                <PlusIcon className="w-5 h-5" />
                Add All
                  </button>
            </div>
          </div>
        ) : (
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-2" />
              <input
                type="text"
                placeholder="https://linkedin.com/in/username"
                value={newLinkedInUrl}
                onChange={(e) => setNewLinkedInUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddLinkedInUrl()}
                className="w-full pl-10 pr-4 py-3 bg-surface-2 border border-border rounded-lg text-text placeholder-muted-2 focus:outline-none focus:ring-2 focus:ring-brand"
              />
            </div>
            <button
              onClick={() => handleAddLinkedInUrl()}
              disabled={!newLinkedInUrl.trim()}
              className={`px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-2 ${
                newLinkedInUrl.trim()
                  ? 'bg-brand text-on-brand hover:bg-brand-strong'
                  : 'bg-surface-2 text-muted-2 cursor-not-allowed'
              }`}
            >
              <PlusIcon className="w-5 h-5" />
              Add & Enrich
            </button>
          </div>
        )}
            </div>

      {/* LinkedIn Profiles List */}
      {linkedInProfiles.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-text">
              Added Profiles ({linkedInProfiles.length})
            </h3>
            {cachedCount > 0 && (
              <span className="text-xs text-success bg-success/10 px-2 py-1 rounded-full">
                {cachedCount} from cache (no API call)
              </span>
            )}
          </div>
          
          <div className="space-y-3">
            {linkedInProfiles.map((profile) => (
              <div
                key={profile.url}
                className={`p-4 rounded-lg border-2 transition-all ${
                  profile.status === 'enriched'
                    ? 'border-success/30 bg-success/5'
                    : profile.status === 'error'
                    ? 'border-error/30 bg-error/5'
                    : 'border-border bg-surface-2'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {profile.status === 'enriched' ? (
                      <>
                    <div className="flex items-center gap-2 mb-1">
                          <CheckCircleIcon className="w-5 h-5 text-success" />
                          <h4 className="font-semibold text-text">{profile.name || 'Unknown'}</h4>
                          {profile.cached && (
                            <span className="text-xs text-success bg-success/10 px-2 py-0.5 rounded-full">
                              cached
                        </span>
                      )}
                    </div>
                        <p className="text-sm text-muted-2 mb-2">
                          {profile.title}{profile.company && ` at ${profile.company}`}
                          {profile.experience && ` • ${profile.experience}y experience`}
                        </p>
                        {profile.skills && profile.skills.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {profile.skills.slice(0, 6).map((skill, idx) => (
                          <span
                            key={idx}
                                className="px-2 py-0.5 text-xs bg-brand/10 text-brand rounded"
                          >
                            {skill}
                          </span>
                        ))}
                            {profile.skills.length > 6 && (
                          <span className="px-2 py-0.5 text-xs text-muted-2">
                                +{profile.skills.length - 6} more
                          </span>
                            )}
                          </div>
                        )}
                        <a
                          href={profile.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-brand hover:underline truncate block"
                        >
                          {profile.url}
                        </a>
                      </>
                    ) : profile.status === 'enriching' ? (
                      <div className="flex items-center gap-3">
                        <div className="animate-spin rounded-full h-5 w-5 border-2 border-brand border-t-transparent" />
                        <div>
                          <p className="text-sm text-text">Enriching profile...</p>
                          <a
                            href={profile.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-muted-2 hover:underline truncate block"
                          >
                            {profile.url}
                          </a>
                        </div>
                      </div>
                    ) : (
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <XMarkIcon className="w-5 h-5 text-error" />
                          <span className="text-sm text-error font-medium">
                            {profile.error || 'Enrichment failed'}
                          </span>
                        </div>
                        <a
                          href={profile.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-muted-2 hover:underline truncate block"
                        >
                          {profile.url}
                        </a>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {profile.status === 'error' && (
                      <button
                        onClick={() => handleRetryEnrichment(profile.url)}
                        className="p-2 text-muted-2 hover:text-brand hover:bg-brand/10 rounded-lg transition-colors"
                        title="Retry enrichment"
                      >
                        <ArrowPathIcon className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => handleRemoveLinkedInUrl(profile.url)}
                      className="p-2 text-muted-2 hover:text-error hover:bg-error/10 rounded-lg transition-colors"
                      title="Remove"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {linkedInProfiles.length === 0 && (
        <div className="text-center py-12 text-muted-2 bg-surface border border-border rounded-lg">
          <LinkIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="font-medium">No LinkedIn profiles added yet</p>
          <p className="text-sm mt-1">Add LinkedIn URLs above to get started</p>
        </div>
      )}

          {/* Continue Button for Create Mode */}
          <div className="flex items-center justify-between pt-4 border-t border-border">
            <div className="text-sm text-muted-2">
              {enrichedCount > 0 && (
                <span className="text-success">
                  ✓ {enrichedCount} profile{enrichedCount !== 1 ? 's' : ''} enriched
                  {cachedCount > 0 && ` (${cachedCount} from cache)`}
                </span>
              )}
            </div>
            <button
              onClick={handleContinueWithNewProfiles}
              disabled={!canContinueCreate}
              className={`px-8 py-3 rounded-lg font-medium transition-colors text-lg ${
                canContinueCreate
                  ? 'bg-brand text-on-brand hover:bg-brand-strong'
                  : 'bg-surface-2 text-muted-2 cursor-not-allowed'
              }`}
            >
              Save Blueprint & Continue →
            </button>
          </div>
        </>
      )}

      {/* Blueprint Name Prompt Modal */}
      {showNamePrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-surface border border-border rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-text mb-2">Name Your Blueprint</h3>
            <p className="text-sm text-muted-2 mb-4">
              Give this blueprint a memorable name so you can reuse it in future analyses.
            </p>
            <input
              type="text"
              value={newBlueprintName}
              onChange={(e) => setNewBlueprintName(e.target.value)}
              placeholder="e.g., Senior Engineer Blueprint"
              className="w-full px-4 py-3 bg-surface-2 border border-border rounded-lg text-text placeholder-muted-2 focus:outline-none focus:ring-2 focus:ring-brand mb-4"
              autoFocus
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowNamePrompt(false);
                  setNewBlueprintName('');
                }}
                className="px-4 py-2 text-muted-2 hover:text-text transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateBlueprint}
                disabled={!newBlueprintName.trim() || isCreatingBlueprint}
                className={`px-6 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
                  newBlueprintName.trim() && !isCreatingBlueprint
                    ? 'bg-brand text-on-brand hover:bg-brand-strong'
                    : 'bg-surface-2 text-muted-2 cursor-not-allowed'
                }`}
              >
                {isCreatingBlueprint && (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-on-brand border-t-transparent" />
                )}
                Create & Continue
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
