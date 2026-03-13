/**
 * Persona Definition Form
 * 
 * Manual persona definition with skills, experience, companies, etc.
 */

import React, { useState } from 'react';
import { UserGroupIcon, SparklesIcon, ArrowLeftIcon, PlusIcon, XMarkIcon } from '@heroicons/react/24/outline';

interface PersonaDefinitionFormProps {
  onSubmit: (persona: any) => void;
  onBack: () => void;
}

export function PersonaDefinitionForm({ onSubmit, onBack }: PersonaDefinitionFormProps) {
  const [persona, setPersona] = useState({
    job_titles: [] as string[],
    skills: [] as string[],
    companies: [] as string[],
    min_years_experience: null as number | null,
    max_years_experience: null as number | null,
    education_level: "",
    location: '',
    description: '', // Free text description
  });

  const [currentInput, setCurrentInput] = useState({ jobTitle: '', skill: '', company: '' });

  const handleAddItem = (field: 'job_titles' | 'skills' | 'companies', value: string) => {
    if (!value.trim()) return;
    setPersona({
      ...persona,
      [field]: [...persona[field], value.trim()],
    });
    setCurrentInput({ ...currentInput, [field === 'job_titles' ? 'jobTitle' : field === 'skills' ? 'skill' : 'company']: '' });
  };

  const handleRemoveItem = (field: 'job_titles' | 'skills' | 'companies', index: number) => {
    setPersona({
      ...persona,
      [field]: persona[field].filter((_, i) => i !== index),
    });
  };

  const handleSubmit = () => {
    // Allow submission even if fields are empty - description might be enough
    onSubmit(persona);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="p-2 hover:bg-surface-3 rounded-lg transition-colors">
          <ArrowLeftIcon className="w-5 h-5 text-muted-2" />
        </button>
        <div>
          <h2 className="text-xl font-semibold text-foreground">Define Ideal Persona</h2>
          <p className="text-muted text-sm">
            Specify the exact attributes you're looking for in candidates
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Job Titles */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Job Titles * (e.g., "Senior Software Engineer")
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={currentInput.jobTitle}
              onChange={(e) => setCurrentInput({ ...currentInput, jobTitle: e.target.value })}
              onKeyPress={(e) => e.key === 'Enter' && handleAddItem('job_titles', currentInput.jobTitle)}
              placeholder="Add job title"
              className="flex-1 px-4 py-2.5 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
            />
            <button 
              onClick={() => handleAddItem('job_titles', currentInput.jobTitle)} 
              className="px-4 py-2.5 bg-brand text-on-brand rounded-lg hover:bg-brand-hover transition-colors font-medium"
            >
              <PlusIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {persona.job_titles.map((title, idx) => (
              <span key={idx} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm flex items-center gap-2">
                {title}
                <button onClick={() => handleRemoveItem('job_titles', idx)}>
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Skills */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Required Skills * (e.g., "Python", "AWS")
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={currentInput.skill}
              onChange={(e) => setCurrentInput({ ...currentInput, skill: e.target.value })}
              onKeyPress={(e) => e.key === 'Enter' && handleAddItem('skills', currentInput.skill)}
              placeholder="Add skill"
              className="flex-1 px-4 py-2.5 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
            />
            <button 
              onClick={() => handleAddItem('skills', currentInput.skill)} 
              className="px-4 py-2.5 bg-brand text-on-brand rounded-lg hover:bg-brand-hover transition-colors font-medium"
            >
              <PlusIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {persona.skills.map((skill, idx) => (
              <span key={idx} className="px-3 py-1 bg-success/10 text-success rounded-full text-sm flex items-center gap-2">
                {skill}
                <button onClick={() => handleRemoveItem('skills', idx)}>
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Target Companies */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Target Companies (e.g., "Google", "Amazon")
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={currentInput.company}
              onChange={(e) => setCurrentInput({ ...currentInput, company: e.target.value })}
              onKeyPress={(e) => e.key === 'Enter' && handleAddItem('companies', currentInput.company)}
              placeholder="Add company"
              className="flex-1 px-4 py-2.5 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
            />
            <button 
              onClick={() => handleAddItem('companies', currentInput.company)} 
              className="px-4 py-2.5 bg-brand text-on-brand rounded-lg hover:bg-brand-hover transition-colors font-medium"
            >
              <PlusIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {persona.companies.map((company, idx) => (
              <span key={idx} className="px-3 py-1 bg-info/10 text-info rounded-full text-sm flex items-center gap-2">
                {company}
                <button onClick={() => handleRemoveItem('companies', idx)}>
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Experience Range */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Years of Experience
          </label>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Minimum</label>
              <input
                type="number"
                value={persona.min_years_experience ?? ''}
                onChange={(e) => setPersona({ ...persona, min_years_experience: e.target.value ? parseInt(e.target.value) : null })}
                placeholder="e.g., 5"
                min="0"
                className="w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Maximum</label>
              <input
                type="number"
                value={persona.max_years_experience ?? ''}
                onChange={(e) => setPersona({ ...persona, max_years_experience: e.target.value ? parseInt(e.target.value) : null })}
                placeholder="e.g., 10"
                min="0"
                className="w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
              />
            </div>
          </div>
        </div>

        {/* Education */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Education Level
          </label>
          <select
            value={persona.education_level}
            onChange={(e) => setPersona({ ...persona, education_level: e.target.value })}
            className="w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
          >
            <option value="">Select education level</option>
            <option>High School</option>
            <option>Associate's</option>
            <option>Bachelor's</option>
            <option>Master's</option>
            <option>PhD</option>
          </select>
        </div>

        {/* Location */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Location (Optional)
          </label>
          <input
            type="text"
            value={persona.location}
            onChange={(e) => setPersona({ ...persona, location: e.target.value })}
            placeholder="e.g., United States, California"
            className="w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
          />
        </div>
      </div>

      {/* Free-form Description */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Describe Your Ideal Candidate (Optional)
        </label>
        <p className="text-xs text-muted mb-2">
          Tell us about your ideal candidate like you would describe them to a friend in a few phrases
        </p>
        <textarea
          value={persona.description}
          onChange={(e) => setPersona({ ...persona, description: e.target.value })}
          placeholder="e.g., 'Someone who's passionate about machine learning, has experience building production ML systems, and can work independently. They should be a strong communicator who can explain complex concepts to non-technical stakeholders.'"
          rows={4}
          className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2 resize-none"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-6 mt-6 border-t border-border">
        <button 
          onClick={onBack}
          className="px-4 py-2 text-muted-2 hover:text-text transition-colors font-medium"
        >
          ← Back
        </button>
        <button
          onClick={handleSubmit}
          className="px-6 py-2.5 rounded-lg font-medium transition-all bg-brand text-on-brand hover:bg-brand-strong shadow-sm hover:shadow-md"
        >
          Confirm Ideal Persona
        </button>
      </div>
    </div>
  );
}

