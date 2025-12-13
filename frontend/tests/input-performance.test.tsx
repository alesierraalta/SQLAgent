import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Page from '../app/page';
import { vi, describe, it, expect } from 'vitest';
import React from 'react';

// Mock IntersectionObserver
const IntersectionObserverMock = vi.fn(() => ({
  disconnect: vi.fn(),
  observe: vi.fn(),
  takeRecords: vi.fn(),
  unobserve: vi.fn(),
}));

vi.stubGlobal('IntersectionObserver', IntersectionObserverMock);

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock dependencies that might cause issues in jsdom
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

// Mock framer-motion to avoid animation delays in tests? 
// Maybe not needed if we just measure input time, but animations might trigger updates.
// For now, let's run with real components.

describe('Input Performance', () => {
  it('measures typing latency', async () => {
    render(<Page />);
    
    const textarea = screen.getByPlaceholderText(/Top 10 productos/i);
    const textToType = 'Select * from products where price > 100 limit 10'; // 47 chars
    
    const start = performance.now();
    // type with delay=0 to simulate fast typing
    await userEvent.type(textarea, textToType, { delay: 0 });
    const end = performance.now();
    
    const duration = end - start;
    console.log(`Typing ${textToType.length} chars took ${duration.toFixed(2)}ms`);
    
    expect(duration).toBeGreaterThan(0);
  });
});
