import React, { Fragment, ReactNode } from 'react';
import { Menu, Transition } from '@headlessui/react';
import { cn } from '../../shared/lib/cn';
import './SolidDropdown.css';

export interface DropdownOption {
  key: string;
  label: string;
  description?: string;
  available?: boolean;
  badge?: string;
  onClick: () => void;
}

interface SolidDropdownProps {
  trigger: ReactNode;
  options: DropdownOption[];
  align?: 'left' | 'right';
  width?: string;
  disabled?: boolean;
  dataLoc?: string;
  menuDataLoc?: string;
  optionDataLocPrefix?: string;
}

const DEFAULT_DROPDOWN_WIDTH = '320px';

/**
 * SolidDropdown - A reusable dropdown component with solid, opaque backgrounds
 *
 * This component uses inline styles to override the app's glass/transparent theme
 * and ensure the dropdown menu is always readable with a solid background.
 *
 * @example
 * ```tsx
 * <SolidDropdown
 *   trigger={<button>Open Menu</button>}
 *   options={[
 *     { key: '1', label: 'Option 1', onClick: () => {} },
 *     { key: '2', label: 'Option 2', description: 'With description', onClick: () => {} }
 *   ]}
 * />
 * ```
 */
export function SolidDropdown({
  trigger,
  options,
  align = 'right',
  width = DEFAULT_DROPDOWN_WIDTH,
  disabled = false,
  dataLoc,
  menuDataLoc,
  optionDataLocPrefix,
}: SolidDropdownProps) {
  const dropdownStyle = width !== DEFAULT_DROPDOWN_WIDTH
    ? ({ '--solid-dropdown-width': width } as React.CSSProperties)
    : undefined;

  return (
    <Menu as="div" className="relative" data-loc={dataLoc}>
      {({ open }) => (
        <>
          <Menu.Button as="div" disabled={disabled} className="focus:outline-none">
            {trigger}
          </Menu.Button>

          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items
              className={cn(
                'solid-dropdown-menu absolute z-[9999] mt-2 origin-top-right rounded-xl shadow-2xl focus:outline-none',
                align === 'right' ? 'right-0' : 'left-0'
              )}
              style={dropdownStyle}
              data-loc={menuDataLoc}
            >
              <div className="solid-dropdown-inner p-3 space-y-2">
                {options.map((option) => {
                  const isAvailable = option.available !== false;
                  const optionDataLoc = optionDataLocPrefix ? `${optionDataLocPrefix}::${option.key}` : undefined;

                  return (
                    <Menu.Item key={option.key} disabled={!isAvailable}>
                      {({ active }) => (
                        <button
                          type="button"
                          onClick={isAvailable ? option.onClick : undefined}
                          disabled={!isAvailable}
                          className={cn(
                            'solid-dropdown-item w-full rounded-lg px-4 py-3 text-left transition-all focus:outline-none',
                            isAvailable ? 'solid-dropdown-item-interactive' : 'solid-dropdown-item-disabled',
                            active && isAvailable && 'solid-dropdown-item-active'
                          )}
                          data-loc={optionDataLoc}
                          data-state={isAvailable ? 'available' : 'unavailable'}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <p className="solid-dropdown-item-label mb-1 text-sm font-semibold">
                                {option.label}
                              </p>
                              {option.description && (
                                <p className="solid-dropdown-item-description text-xs leading-relaxed">
                                  {option.description}
                                </p>
                              )}
                            </div>
                            {option.badge && (
                              <span className="solid-dropdown-badge flex-shrink-0 px-2 py-1 text-[10px] font-bold uppercase tracking-wider">
                                {option.badge}
                              </span>
                            )}
                          </div>
                        </button>
                      )}
                    </Menu.Item>
                  );
                })}
              </div>
            </Menu.Items>
          </Transition>
        </>
      )}
    </Menu>
  );
}
