import { Menu, Transition } from '@headlessui/react';
import { Fragment, type CSSProperties, type ReactNode } from 'react';
import { cn } from '../../shared/lib/cn';
import './ReadableDropdown.css';

export interface ReadableDropdownOption {
  key: string;
  label: string;
  description?: string;
  onClick: () => void;
}

interface ReadableDropdownProps {
  trigger: ReactNode;
  options: ReadableDropdownOption[];
  align?: 'left' | 'right';
  width?: string;
  disabled?: boolean;
}

export function ReadableDropdown({
  trigger,
  options,
  align = 'right',
  width,
  disabled = false,
}: ReadableDropdownProps) {
  const menuStyle: CSSProperties | undefined = width
    ? ({
        '--readable-dropdown-width': width,
      } as CSSProperties)
    : undefined;

  return (
    <Menu as="div" className="relative readable-dropdown">
      {() => (
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
                'readable-dropdown-menu absolute mt-2 origin-top-right focus:outline-none',
                align === 'right' ? 'right-0' : 'left-0'
              )}
              style={menuStyle}
            >
              <div className="readable-dropdown-options">
                {options.map((option) => (
                  <Menu.Item key={option.key}>
                    {({ active }) => (
                      <button
                        type="button"
                        onClick={option.onClick}
                        className={cn(
                          'readable-dropdown-option',
                          active && 'readable-dropdown-option-active'
                        )}
                      >
                        <div className="readable-dropdown-content">
                          <div className="readable-dropdown-copy">
                            <p className="readable-dropdown-label">{option.label}</p>
                            {option.description && (
                              <p className="readable-dropdown-description">{option.description}</p>
                            )}
                          </div>
                        </div>
                      </button>
                    )}
                  </Menu.Item>
                ))}
              </div>
            </Menu.Items>
          </Transition>
        </>
      )}
    </Menu>
  );
}
