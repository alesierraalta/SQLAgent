"use client";

import { useState, useEffect } from "react";
import { useSettingsStore } from "@/lib/store";

export function ViewSettings() {
  const [isOpen, setIsOpen] = useState(false);
  const settings = useSettingsStore();
  
  // Hydration fix for zustand persist
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // Close on click outside (simple implementation)
  useEffect(() => {
    const close = () => setIsOpen(false);
    if (isOpen) {
      window.addEventListener('click', close);
    }
    return () => window.removeEventListener('click', close);
  }, [isOpen]);

  if (!mounted) return null;

  return (
    <div className="relative inline-block text-left" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex justify-center w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
      >
        View Options
        <svg className="-mr-1 ml-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 z-50 w-64 mt-2 origin-top-right bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
          <div className="py-1">
            <div className="px-4 py-3 border-b border-gray-100">
              <div className="flex items-center justify-between">
                <label htmlFor="simple-mode" className="text-sm font-bold text-gray-900 cursor-pointer">
                  Simple Mode
                </label>
                <div className="relative inline-block w-10 mr-2 align-middle select-none transition duration-200 ease-in">
                    <input 
                        type="checkbox" 
                        name="simple-mode" 
                        id="simple-mode" 
                        className="toggle-checkbox absolute block w-5 h-5 rounded-full bg-white border-4 appearance-none cursor-pointer checked:right-0 checked:border-blue-600"
                        style={{right: settings.simpleMode ? '0' : 'auto', left: settings.simpleMode ? 'auto' : '0', borderColor: settings.simpleMode ? '#2563EB' : '#D1D5DB'}}
                        checked={settings.simpleMode}
                        onChange={(e) => settings.setSimpleMode(e.target.checked)}
                    />
                    <label htmlFor="simple-mode" className={`toggle-label block overflow-hidden h-5 rounded-full cursor-pointer ${settings.simpleMode ? 'bg-blue-600' : 'bg-gray-300'}`}></label>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-1">Hide all technical details</p>
            </div>

            <div className={`px-4 py-2 space-y-3 transition-opacity duration-200 ${settings.simpleMode ? 'opacity-40 pointer-events-none' : ''}`}>
              <Toggle
                label="Thinking Process"
                checked={settings.showThinking}
                onChange={settings.toggleThinking}
              />
              <Toggle
                label="SQL Query"
                checked={settings.showSQL}
                onChange={settings.toggleSQL}
              />
              <Toggle
                label="Raw Data Table"
                checked={settings.showData}
                onChange={settings.toggleData}
              />
              <Toggle
                label="Visualizations"
                checked={settings.showVisualization}
                onChange={settings.toggleVisualization}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <div className="flex items-center justify-between cursor-pointer" onClick={onChange}>
      <span className="text-sm text-gray-700">{label}</span>
      <div className={`w-9 h-5 flex items-center bg-gray-300 rounded-full p-1 duration-300 ease-in-out ${checked ? 'bg-blue-500' : ''}`}>
        <div className={`bg-white w-3 h-3 rounded-full shadow-md transform duration-300 ease-in-out ${checked ? 'translate-x-4' : ''}`}></div>
      </div>
    </div>
  );
}
