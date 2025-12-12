import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SettingsState {
  simpleMode: boolean
  showThinking: boolean
  showSQL: boolean
  showData: boolean
  showVisualization: boolean
  
  setSimpleMode: (enabled: boolean) => void
  toggleThinking: () => void
  toggleSQL: () => void
  toggleData: () => void
  toggleVisualization: () => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      simpleMode: false,
      showThinking: true,
      showSQL: true,
      showData: true,
      showVisualization: true,

      setSimpleMode: (enabled) => set({ simpleMode: enabled }),
      toggleThinking: () => set((state) => ({ showThinking: !state.showThinking })),
      toggleSQL: () => set((state) => ({ showSQL: !state.showSQL })),
      toggleData: () => set((state) => ({ showData: !state.showData })),
      toggleVisualization: () => set((state) => ({ showVisualization: !state.showVisualization })),
    }),
    {
      name: 'llm-dw-settings',
    }
  )
)
