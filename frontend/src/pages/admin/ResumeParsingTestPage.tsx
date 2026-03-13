/**
 * Resume Parsing Test Page
 * 
 * Admin tool for testing and iterating on Docling resume parsing quality.
 * Upload a resume PDF and see detailed parsing output.
 */

import React, { useState } from 'react';
import {
  CloudArrowUpIcon,
  DocumentIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { SectionHeader } from '../../components/common/SectionHeader';
import { useToasts } from '../../stores/useToasts';

interface ContactInfo {
  full_name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  location?: string | null;
}

interface Experience {
  title?: string | null;
  company?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  is_current?: boolean;
  description?: string | null;
  location?: string | null;
}

interface Education {
  degree?: string | null;
  field_of_study?: string | null;
  school?: string | null;
  start_date?: string | null;
  end_date?: string | null;
}

interface QualityAssessment {
  has_contact_info: boolean;
  skills_count: number;
  experience_count: number;
  education_count: number;
  certifications_count: number;
  issues: string[];
  quality_score: number;
}

interface ParsedResumeResponse {
  success: boolean;
  filename: string;
  file_size: number;
  raw_markdown?: string | null;
  contact_info: ContactInfo;
  skills: string[];
  experience: Experience[];
  education: Education[];
  certifications: string[];
  summary?: string | null;
  parsed_resume: Record<string, any>;
  pdl_format: Record<string, any>;
  quality_assessment: QualityAssessment;
  docling_output?: Record<string, any> | null;
}

export const ResumeParsingTestPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [parseResult, setParseResult] = useState<ParsedResumeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Collapsible sections
  const [expandedSections, setExpandedSections] = useState({
    markdown: false,
    contact: true,
    skills: true,
    experience: true,
    education: true,
    certifications: true,
    pdl: false,
    docling: false,
  });
  
  const { push: addToast } = useToasts();

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      
      // Validate file type
      if (!['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'].includes(selectedFile.type)) {
        setError('Please upload a PDF, DOCX, or TXT file');
        return;
      }
      
      // Validate file size (10MB limit)
      if (selectedFile.size > 10 * 1024 * 1024) {
        setError('File too large. Maximum size: 10MB');
        return;
      }
      
      setFile(selectedFile);
      setError(null);
      setParseResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/admin/test-resume-parsing', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to parse resume');
      }

      const result: ParsedResumeResponse = await response.json();
      setParseResult(result);
      
      addToast({
        kind: 'success',
        message: `Resume parsed successfully! Quality score: ${result.quality_assessment.quality_score}%`,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      addToast({
        kind: 'error',
        message: `Failed to parse resume: ${errorMessage}`,
      });
    } finally {
      setIsUploading(false);
    }
  };

  const getQualityColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    addToast({
      kind: 'success',
      message: `${label} copied to clipboard`,
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <SectionHeader
        title="Resume Parsing Test"
        description="Test Docling resume parsing quality. Upload a resume and see detailed extraction results to iterate on parsing logic."
      />

      {/* Upload Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Resume</h3>
        
        <div className="flex items-center gap-4">
          <label className="flex-1">
            <div className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              file ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
            }`}>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
                className="hidden"
              />
              <CloudArrowUpIcon className="w-12 h-12 mx-auto text-gray-400 mb-2" />
              {file ? (
                <div>
                  <DocumentIcon className="w-6 h-6 inline mr-2 text-blue-600" />
                  <span className="text-sm font-medium text-gray-900">{file.name}</span>
                  <span className="text-xs text-gray-500 block mt-1">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
              ) : (
                <div>
                  <p className="text-sm text-gray-600">
                    Click to upload or drag and drop
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    PDF, DOCX, or TXT (max 10MB)
                  </p>
                </div>
              )}
            </div>
          </label>

          <button
            onClick={handleUpload}
            disabled={!file || isUploading}
            className="btn-primary px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? 'Parsing...' : 'Parse Resume'}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <ExclamationCircleIcon className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <span className="text-sm text-red-800">{error}</span>
          </div>
        )}
      </div>

      {/* Results Section */}
      {parseResult && (
        <div className="space-y-6">
          {/* Quality Assessment */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Quality Assessment</h3>
            
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold text-gray-900">
                  {parseResult.quality_assessment.skills_count}
                </div>
                <div className="text-sm text-gray-600">Skills</div>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold text-gray-900">
                  {parseResult.quality_assessment.experience_count}
                </div>
                <div className="text-sm text-gray-600">Experience</div>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold text-gray-900">
                  {parseResult.quality_assessment.education_count}
                </div>
                <div className="text-sm text-gray-600">Education</div>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <span className="text-sm font-medium text-gray-700">Overall Quality Score</span>
              <span className={`text-2xl font-bold ${getQualityColor(parseResult.quality_assessment.quality_score)}`}>
                {parseResult.quality_assessment.quality_score}%
              </span>
            </div>

            {parseResult.quality_assessment.issues.length > 0 && (
              <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <h4 className="text-sm font-semibold text-yellow-900 mb-2">Issues Found:</h4>
                <ul className="space-y-1">
                  {parseResult.quality_assessment.issues.map((issue, idx) => (
                    <li key={idx} className="text-sm text-yellow-800 flex items-start gap-2">
                      <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Contact Information */}
          <CollapsibleSection
            title="Contact Information"
            isExpanded={expandedSections.contact}
            onToggle={() => toggleSection('contact')}
          >
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <DataField label="Full Name" value={parseResult.contact_info.full_name} />
              <DataField label="Email" value={parseResult.contact_info.email} />
              <DataField label="Phone" value={parseResult.contact_info.phone} />
              <DataField label="LinkedIn" value={parseResult.contact_info.linkedin_url} isLink />
              <DataField label="GitHub" value={parseResult.contact_info.github_url} isLink />
              <DataField label="Location" value={parseResult.contact_info.location} />
            </dl>
          </CollapsibleSection>

          {/* Skills */}
          <CollapsibleSection
            title={`Skills (${parseResult.skills.length})`}
            isExpanded={expandedSections.skills}
            onToggle={() => toggleSection('skills')}
          >
            {parseResult.skills.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {parseResult.skills.map((skill, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1 bg-blue-100 text-blue-800 text-sm rounded-full"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No skills extracted</p>
            )}
          </CollapsibleSection>

          {/* Experience */}
          <CollapsibleSection
            title={`Work Experience (${parseResult.experience.length})`}
            isExpanded={expandedSections.experience}
            onToggle={() => toggleSection('experience')}
          >
            {parseResult.experience.length > 0 ? (
              <div className="space-y-4">
                {parseResult.experience.map((exp, idx) => (
                  <div key={idx} className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-semibold text-gray-900">{exp.title || 'Unknown Title'}</h4>
                    <p className="text-sm text-gray-600">{exp.company || 'Unknown Company'}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {exp.start_date || '?'} - {exp.is_current ? 'Present' : (exp.end_date || '?')}
                    </p>
                    {exp.description && (
                      <p className="text-sm text-gray-700 mt-2 line-clamp-3">{exp.description}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No experience extracted</p>
            )}
          </CollapsibleSection>

          {/* Education */}
          <CollapsibleSection
            title={`Education (${parseResult.education.length})`}
            isExpanded={expandedSections.education}
            onToggle={() => toggleSection('education')}
          >
            {parseResult.education.length > 0 ? (
              <div className="space-y-4">
                {parseResult.education.map((edu, idx) => (
                  <div key={idx} className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-semibold text-gray-900">{edu.degree || 'Unknown Degree'}</h4>
                    <p className="text-sm text-gray-600">{edu.school || 'Unknown School'}</p>
                    {edu.field_of_study && (
                      <p className="text-sm text-gray-600">{edu.field_of_study}</p>
                    )}
                    <p className="text-xs text-gray-500 mt-1">{edu.end_date || 'Unknown'}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No education extracted</p>
            )}
          </CollapsibleSection>

          {/* Certifications */}
          {parseResult.certifications.length > 0 && (
            <CollapsibleSection
              title={`Certifications (${parseResult.certifications.length})`}
              isExpanded={expandedSections.certifications}
              onToggle={() => toggleSection('certifications')}
            >
              <ul className="space-y-2">
                {parseResult.certifications.map((cert, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <CheckCircleIcon className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">{cert}</span>
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Raw Markdown */}
          <CollapsibleSection
            title="Raw Markdown Output"
            isExpanded={expandedSections.markdown}
            onToggle={() => toggleSection('markdown')}
          >
            {parseResult.raw_markdown ? (
              <div>
                <button
                  onClick={() => copyToClipboard(parseResult.raw_markdown!, 'Markdown')}
                  className="mb-2 text-xs text-blue-600 hover:text-blue-700"
                >
                  Copy to clipboard
                </button>
                <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto max-h-96 text-xs">
                  {parseResult.raw_markdown}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-gray-500">No markdown output</p>
            )}
          </CollapsibleSection>

          {/* PDL Format */}
          <CollapsibleSection
            title="PDL-Normalized Format (JSON)"
            isExpanded={expandedSections.pdl}
            onToggle={() => toggleSection('pdl')}
          >
            <button
              onClick={() => copyToClipboard(JSON.stringify(parseResult.pdl_format, null, 2), 'PDL JSON')}
              className="mb-2 text-xs text-blue-600 hover:text-blue-700"
            >
              Copy to clipboard
            </button>
            <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto max-h-96 text-xs">
              {JSON.stringify(parseResult.pdl_format, null, 2)}
            </pre>
          </CollapsibleSection>

          {/* Docling Output */}
          {parseResult.docling_output && (
            <CollapsibleSection
              title="Docling Output Structure (JSON)"
              isExpanded={expandedSections.docling}
              onToggle={() => toggleSection('docling')}
            >
              <button
                onClick={() => copyToClipboard(JSON.stringify(parseResult.docling_output, null, 2), 'Docling JSON')}
                className="mb-2 text-xs text-blue-600 hover:text-blue-700"
              >
                Copy to clipboard
              </button>
              <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto max-h-96 text-xs">
                {JSON.stringify(parseResult.docling_output, null, 2)}
              </pre>
            </CollapsibleSection>
          )}
        </div>
      )}
    </div>
  );
};

// Helper Components

interface CollapsibleSectionProps {
  title: string;
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  title,
  isExpanded,
  onToggle,
  children,
}) => {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {isExpanded ? (
          <ChevronDownIcon className="w-5 h-5 text-gray-500" />
        ) : (
          <ChevronRightIcon className="w-5 h-5 text-gray-500" />
        )}
      </button>
      {isExpanded && <div className="p-4 border-t border-gray-200">{children}</div>}
    </div>
  );
};

interface DataFieldProps {
  label: string;
  value?: string | null;
  isLink?: boolean;
}

const DataField: React.FC<DataFieldProps> = ({ label, value, isLink }) => {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500 uppercase">{label}</dt>
      <dd className="mt-1 text-sm text-gray-900">
        {value ? (
          isLink ? (
            <a href={value} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-700">
              {value}
            </a>
          ) : (
            value
          )
        ) : (
          <span className="text-gray-400 italic">Not extracted</span>
        )}
      </dd>
    </div>
  );
};

