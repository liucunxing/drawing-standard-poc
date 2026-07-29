import '@testing-library/jest-dom/vitest'

const getComputedStyle = window.getComputedStyle.bind(window)
Object.defineProperty(window, 'getComputedStyle', {
  configurable: true,
  value: (element: Element) => getComputedStyle(element),
})
