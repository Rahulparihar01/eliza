/**
 * Theme Settings Page
 * 
 * Allows tenant admins to customize the platform's color scheme.
 * Theme settings are scoped to the tenant and apply to all users.
 * 
 * Permission-gated: requires theme:write permission
 */

import React, { useState, useEffect } from 'react';
import {
  SparklesIcon,
  ArrowPathIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';
import { useToasts } from '../../stores/useToasts';
import { useTheme, ThemeColors, THEME_PRESETS, DEFAULT_THEME } from '../../stores/useTheme';
import {
  Button,
  Input,
  Label,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Badge,
  Spinner,
  Page,
  PageHeader,
  PageBody,
} from '../../components/ui';

// Preset display names
const PRESET_DISPLAY_NAMES: Record<string, string> = {
  'eliza-forge': 'Eliza Forge',
  'ocean-blue': 'Ocean Blue',
  'forest-green': 'Forest Green',
  'royal-purple': 'Royal Purple',
};

// Clean color swatch component that hides browser chrome
interface ColorSwatchProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
}

function ColorSwatch({ id, value, onChange }: ColorSwatchProps) {
  return (
    <div className="relative w-10 h-10 rounded-full overflow-hidden border-2 border-gray-200 dark:border-dark-border shadow-sm hover:shadow-md transition-shadow cursor-pointer">
      {/* Color preview circle */}
      <div 
        className="absolute inset-0 rounded-full"
        style={{ backgroundColor: value }}
      />
      {/* Hidden native color input - covers the entire area for click handling */}
      <input
        type="color"
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      />
    </div>
  );
}

export default function ThemePage() {
  const { colors: savedColors, preset: savedPreset, saveTheme, isLoading } = useTheme();
  const pushToast = useToasts((s) => s.push);
  
  // Local state for editing (allows preview without saving)
  const [localColors, setLocalColors] = useState<ThemeColors>(savedColors);
  const [localPreset, setLocalPreset] = useState<string | null>(savedPreset);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // Sync local state when saved colors change (on load or after save)
  useEffect(() => {
    setLocalColors(savedColors);
    setLocalPreset(savedPreset);
  }, [savedColors, savedPreset]);
  
  // Detect unsaved changes
  useEffect(() => {
    const changed = 
      localColors.primary !== savedColors.primary ||
      localColors.primaryLight !== savedColors.primaryLight ||
      localColors.accent !== savedColors.accent ||
      localColors.text !== savedColors.text;
    setHasChanges(changed);
  }, [localColors, savedColors]);
  
  // Apply live preview when local colors change
  useEffect(() => {
    // Apply colors to CSS variables for live preview
    const root = document.documentElement;
    root.style.setProperty('--color-primary', hexToRgb(localColors.primary));
    root.style.setProperty('--color-primary-light', hexToRgb(localColors.primaryLight));
    root.style.setProperty('--color-accent', hexToRgb(localColors.accent));
    root.style.setProperty('--color-text', hexToRgb(localColors.text));
  }, [localColors]);
  
  // Utility: Convert hex to RGB
  function hexToRgb(hex: string): string {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!result) return '201 80 107';
    return `${parseInt(result[1], 16)} ${parseInt(result[2], 16)} ${parseInt(result[3], 16)}`;
  }
  
  // Handle individual color change
  const handleColorChange = (key: keyof ThemeColors, value: string) => {
    // Validate hex format (allow partial input while typing)
    if (value.startsWith('#') && value.length <= 7) {
      setLocalColors(prev => ({ ...prev, [key]: value }));
      setLocalPreset(null); // Mark as custom
    }
  };
  
  // Handle preset selection
  const handlePresetSelect = (presetKey: string) => {
    const preset = THEME_PRESETS[presetKey];
    if (preset) {
      setLocalColors(preset);
      setLocalPreset(presetKey);
    }
  };
  
  // Save theme to backend
  const handleSave = async () => {
    setIsSaving(true);
    try {
      await saveTheme(localColors, localPreset);
      pushToast({ 
        kind: 'success', 
        message: 'Theme saved successfully!' 
      });
    } catch (error) {
      pushToast({ 
        kind: 'error', 
        message: error instanceof Error ? error.message : 'Failed to save theme' 
      });
    } finally {
      setIsSaving(false);
    }
  };
  
  // Reset to default Eliza Forge theme
  const handleReset = () => {
    setLocalColors(DEFAULT_THEME);
    setLocalPreset('eliza-forge');
  };
  
  // Discard unsaved changes
  const handleDiscard = () => {
    setLocalColors(savedColors);
    setLocalPreset(savedPreset);
  };
  
  return (
    <Page maxWidth="xl">
      <PageHeader
        title="Theme Settings"
        description="Customize your organization's color scheme"
        actions={
          <div className="flex items-center gap-2">
            {hasChanges && (
              <Button variant="outline" onClick={handleDiscard} disabled={isSaving}>
                Discard
              </Button>
            )}
            <Button onClick={handleSave} disabled={!hasChanges || isSaving}>
              {isSaving ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Saving...
                </>
              ) : (
                <>
                  <CheckIcon className="h-4 w-4 mr-2" />
                  Save Theme
                </>
              )}
            </Button>
          </div>
        }
      />
      <PageBody>
        <Card>
          {/* Gradient accent bar */}
          <div 
            className="h-1"
            style={{
              background: `linear-gradient(to right, ${localColors.primary}, ${localColors.primaryLight}, ${localColors.accent})`
            }}
          />
          
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SparklesIcon className="h-5 w-5 text-eliza-red" />
              Theme Customizer
            </CardTitle>
            <CardDescription>
              Adjust brand colors - changes preview in real-time. Click "Save Theme" to apply.
            </CardDescription>
          </CardHeader>
          
          <CardContent>
            <div className="grid md:grid-cols-2 gap-8">
              {/* Color Pickers */}
              <div className="space-y-4">
                <h4 className="text-sm font-medium text-charcoal dark:text-white">Brand Colors</h4>
                
                <div className="grid grid-cols-2 gap-4">
                  {/* Primary Color */}
                  <div className="space-y-2">
                    <Label htmlFor="primary">Primary</Label>
                    <div className="flex items-center gap-3">
                      <ColorSwatch
                        id="primary"
                        value={localColors.primary}
                        onChange={(v) => handleColorChange('primary', v)}
                      />
                      <Input
                        value={localColors.primary}
                        onChange={(e) => handleColorChange('primary', e.target.value)}
                        className="font-mono text-sm"
                        placeholder="#c9506b"
                      />
                    </div>
                  </div>
                  
                  {/* Primary Light Color */}
                  <div className="space-y-2">
                    <Label htmlFor="primaryLight">Primary Light</Label>
                    <div className="flex items-center gap-3">
                      <ColorSwatch
                        id="primaryLight"
                        value={localColors.primaryLight}
                        onChange={(v) => handleColorChange('primaryLight', v)}
                      />
                      <Input
                        value={localColors.primaryLight}
                        onChange={(e) => handleColorChange('primaryLight', e.target.value)}
                        className="font-mono text-sm"
                        placeholder="#e8a598"
                      />
                    </div>
                  </div>
                  
                  {/* Accent Color */}
                  <div className="space-y-2">
                    <Label htmlFor="accent">Accent</Label>
                    <div className="flex items-center gap-3">
                      <ColorSwatch
                        id="accent"
                        value={localColors.accent}
                        onChange={(v) => handleColorChange('accent', v)}
                      />
                      <Input
                        value={localColors.accent}
                        onChange={(e) => handleColorChange('accent', e.target.value)}
                        className="font-mono text-sm"
                        placeholder="#f5c4a1"
                      />
                    </div>
                  </div>
                  
                  {/* Text Color */}
                  <div className="space-y-2">
                    <Label htmlFor="text">Text</Label>
                    <div className="flex items-center gap-3">
                      <ColorSwatch
                        id="text"
                        value={localColors.text}
                        onChange={(v) => handleColorChange('text', v)}
                      />
                      <Input
                        value={localColors.text}
                        onChange={(e) => handleColorChange('text', e.target.value)}
                        className="font-mono text-sm"
                        placeholder="#5c4a5a"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Presets */}
              <div className="space-y-4">
                <h4 className="text-sm font-medium text-charcoal dark:text-white">Brand Presets</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(THEME_PRESETS).map(([key, colors]) => (
                    <button
                      key={key}
                      onClick={() => handlePresetSelect(key)}
                      className={`
                        flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium
                        border transition-all
                        ${localPreset === key
                          ? 'border-eliza-red bg-eliza-red/10 text-eliza-red'
                          : 'border-gray-200 dark:border-dark-border hover:border-gray-300 dark:hover:border-gray-600 text-charcoal dark:text-gray-300'
                        }
                      `}
                    >
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: colors.primary }}
                      />
                      {PRESET_DISPLAY_NAMES[key] || key}
                    </button>
                  ))}
                </div>
                
                <div className="pt-4">
                  <Button variant="outline" size="sm" onClick={handleReset}>
                    <ArrowPathIcon className="h-4 w-4 mr-2" />
                    Reset to Default
                  </Button>
                </div>
                
                {/* Custom indicator */}
                {!localPreset && (
                  <div className="pt-2">
                    <Badge variant="default">Custom Colors</Badge>
                  </div>
                )}
              </div>
            </div>

            {/* Live Preview */}
            <div className="mt-8 p-4 rounded-xl bg-gray-50 dark:bg-dark-surface-2">
              <div className="flex items-center gap-4 flex-wrap">
                <span className="text-sm text-gray-500 dark:text-gray-400">Live Preview:</span>
                <Button 
                  size="sm"
                  style={{ 
                    backgroundColor: localColors.primary,
                    borderColor: localColors.primary 
                  }}
                  className="text-white hover:opacity-90"
                >
                  Primary Button
                </Button>
                <Button variant="secondary" size="sm">
                  Secondary
                </Button>
                <Badge 
                  style={{ 
                    backgroundColor: `${localColors.primary}20`,
                    color: localColors.primary 
                  }}
                >
                  Brand Badge
                </Badge>
                <span style={{ color: localColors.primary }} className="font-medium">
                  Accent Text
                </span>
                <div 
                  className="h-6 w-32 rounded-full"
                  style={{ 
                    background: `linear-gradient(to right, ${localColors.primary}, ${localColors.primaryLight}, ${localColors.accent})`
                  }}
                />
              </div>
            </div>
            
            {/* Unsaved changes warning */}
            {hasChanges && (
              <div className="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                <p className="text-sm text-amber-700 dark:text-amber-400">
                  You have unsaved changes. Click "Save Theme" to apply them to your organization.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </PageBody>
    </Page>
  );
}
