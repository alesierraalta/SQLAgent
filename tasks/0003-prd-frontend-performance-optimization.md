# Product Requirements Document (PRD): Frontend Performance Analysis & Optimization

## 1. Introduction
Users are reporting significant input lag ("va muy lento") in the question input area of the frontend application. This degrades the user experience, making the application feel unresponsive. This project aims to diagnose the root cause of this slowness, implement automated performance tests to track it, and apply optimizations to ensure a smooth typing experience.

## 2. Goals
- **Diagnose Bottleneck:** Identify the specific code paths or components causing input latency (e.g., excessive re-renders, heavy computation on keypress).
- **Establish Baseline:** Create automated performance tests (benchmarks) to measure input latency and render times.
- **Optimize Responsiveness:** Reduce input delay to perceptible instant levels (target < 50ms processing time per keystroke, ideally < 16ms).
- **Prevent Regression:** Ensure future changes do not re-introduce input lag.

## 3. User Stories
- **As a user**, I want to type my question into the text area without noticing any delay between my keystrokes and the character appearing on screen.
- **As a developer**, I want to run a performance test command that tells me if the input component is too slow, so I can catch performance bugs early.

## 4. Functional Requirements

### 4.1. Performance Testing Infrastructure
1.  **Automated Component Benchmark:** Implement a test using a library like `@testing-library/react` with `user-event` or a dedicated performance tool (e.g., `react-performance-testing`) to measure the time it takes to fire events and update the DOM.
2.  **Scenario:** Simulate rapid typing (e.g., 50 characters in quick succession) and measure the total time to completion or average time per character.

### 4.2. Analysis & Optimization
3.  **Profiling:** Use React DevTools Profiler to identify components that re-render unnecessarily when the input state changes.
4.  **Debouncing/Deferral:** If heavy logic (like validation or derived state calculations) runs on every keystroke, implement debouncing or use `useDeferredValue` to unblock the main thread.
5.  **Component Isolation:** Ensure the text input state is isolated from the rest of the heavy page components (like the Data Table or Terminal) to prevent full-page re-renders on every keystroke.

## 5. Non-Goals
- **Backend Optimization:** This task is strictly focused on the frontend *input* lag. Backend query speed is out of scope for this specific PRD.
- **Visual Redesign:** We are not changing the look of the UI, only its performance characteristics.

## 6. Technical Considerations
- **React State Management:** Currently using `useState` for the input. If this state is lifted too high (e.g., to `Page` root) and passed down to many children without `memo`, it causes the entire page to re-render on every keystroke.
- **Browser Constraints:** JavaScript runs on the main thread. Blocking it with heavy updates causes frame drops (jank).

## 7. Success Metrics
- **Input Latency:** Average processing time per character input < 16ms (60fps target).
- **Re-render Count:** Typing in the input field should NOT trigger re-renders of unrelated components (like `QueryResultTable` or `Terminal` logs).
