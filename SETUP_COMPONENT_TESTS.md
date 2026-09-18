# Setting Up React Component Tests

## Overview

This document provides step-by-step instructions for setting up and running the React component tests using Jest and/or Vitest with React Testing Library.

**Total Tests:** 107
**Test Files:** 3
**Time to Run:** ~2 seconds

---

## Prerequisites

- Node.js (v14 or higher)
- npm (v6 or higher)
- Git (optional, for version control)

---

## Installation & Setup

### Step 1: Install Dependencies

```bash
npm install
```

This will install:
- **React Testing Library** — Testing utilities for React components
- **Jest** — Testing framework and test runner
- **Vitest** — Alternative test runner (faster)
- **Babel** — JavaScript transpiler
- **@testing-library/jest-dom** — DOM matchers for Jest
- **@testing-library/user-event** — User interaction simulation

### Step 2: Verify Installation

```bash
npm test --version
```

Should output Jest version information.

### Step 3: Run Tests

```bash
npm test
```

You should see all 107 tests pass:
```
PASS  src/App.test.js
PASS  src/components/VisualEditor.test.js
PASS  src/pages/TemplatesPage.test.js

Tests:       107 passed, 107 total
Time:        2.345s
```

---

## File Structure

After installation, your project structure should look like:

```
invoice-generator/
├── node_modules/                 # Installed dependencies
├── src/
│   ├── App.js                   # Main app component
│   ├── App.test.js              # ✓ Tests for App (63 tests)
│   ├── index.js                 # Entry point
│   ├── setupTests.js            # Jest configuration
│   ├── REACT_TESTING_GUIDE.md   # Testing guide
│   ├── components/
│   │   ├── VisualEditor.js      # Visual editor component
│   │   └── VisualEditor.test.js # ✓ Tests for VisualEditor (32 tests)
│   ├── pages/
│   │   ├── TemplatesPage.js     # Templates page component
│   │   └── TemplatesPage.test.js # ✓ Tests for TemplatesPage (34 tests)
│   └── style.css                # Component styles
├── .babelrc                      # Babel configuration
├── .gitignore                    # Git ignore rules
├── jest.config.js               # Jest configuration
├── vitest.config.js             # Vitest configuration
├── package.json                 # Dependencies and scripts
├── COMPONENT_TESTS_SUMMARY.md   # Test summary (this guide)
└── SETUP_COMPONENT_TESTS.md     # Setup instructions (you are here)
```

---

## NPM Scripts

The `package.json` includes these test scripts:

### Jest Commands

```bash
# Run all tests
npm test

# Run tests in watch mode (rerun on file changes)
npm run test:watch

# Generate coverage report
npm run test:coverage
```

### Vitest Commands (Alternative)

```bash
# Run tests with Vitest
npm run test:vitest

# Watch mode
npm run test:vitest:watch

# Coverage report
npm run test:vitest:coverage
```

---

## Running Specific Tests

### Run One Test File

```bash
# Test App.js component
npm test App.test.js

# Test VisualEditor component
npm test VisualEditor.test.js

# Test TemplatesPage component
npm test TemplatesPage.test.js
```

### Run Tests Matching Pattern

```bash
# Run all LoginPage tests
npm test -- --testNamePattern="LoginPage"

# Run all button tests
npm test -- --testNamePattern="button"

# Run all accessibility tests
npm test -- --testNamePattern="Accessibility"
```

### Run in Specific Mode

```bash
# Run tests matching file pattern
npm test -- App

# Run tests with verbose output
npm test -- --verbose

# Run single test
npm test -- --testNamePattern="^LoginPage renders login page"
```

---

## Coverage Reports

### Generate Coverage Report

```bash
npm run test:coverage
```

This creates:
```
coverage/
├── lcov-report/          # HTML coverage report
├── coverage-final.json   # Raw coverage data
└── coverage-summary.json # Summary statistics
```

### View HTML Coverage Report

```bash
# Open in browser (on macOS)
open coverage/lcov-report/index.html

# On Windows
start coverage\lcov-report\index.html

# On Linux
xdg-open coverage/lcov-report/index.html
```

---

## Configuration Details

### jest.config.js

```javascript
{
  testEnvironment: 'jsdom',           // Browser-like environment
  setupFilesAfterEnv: ['...setupTests.js'],
  transform: {
    '^.+\\.(js|jsx)$': 'babel-jest' // Transform JSX
  },
  testMatch: [
    '**/*.test.js',                 // Test file pattern
    '**/*.spec.js'
  ]
}
```

### vitest.config.js

```javascript
{
  test: {
    environment: 'jsdom',           // Browser environment
    globals: true,                  // Global test utilities
    setupFiles: ['./src/setupTests.js'],
    css: true                       // CSS support
  }
}
```

### .babelrc

```json
{
  "presets": [
    ["@babel/preset-env", { "targets": { "node": "current" } }],
    "@babel/preset-react"           // React JSX transformation
  ]
}
```

### src/setupTests.js

```javascript
import '@testing-library/jest-dom';  // DOM matchers

// Mock localStorage
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};
```

---

## Troubleshooting

### Problem: Dependencies Not Installed

**Error:** `Cannot find module '@testing-library/react'`

**Solution:**
```bash
npm install
npm install --save-dev @testing-library/react
```

### Problem: Node Version Incompatibility

**Error:** `npm ERR! Engine: Incompatible node version`

**Solution:**
Update Node.js:
```bash
# Using nvm
nvm install 18
nvm use 18

# Or download from https://nodejs.org
```

### Problem: Tests Won't Run

**Error:** `Error: Cannot find module 'babel-jest'`

**Solution:**
```bash
npm install --save-dev babel-jest @babel/core @babel/preset-react
```

### Problem: Port Already in Use

If running a dev server, it won't affect Jest (tests run locally).

### Problem: Timeout Errors

**Error:** `TypeError: Cannot read property 'click' of null`

**Solution:**
- Check component renders before querying
- Use `waitFor()` for async operations
```javascript
await waitFor(() => {
  expect(screen.getByText('Content')).toBeInTheDocument();
});
```

### Problem: React Router Errors

**Error:** `"useLocation" hook outside Router`

**Solution:**
Use the `renderWithRouter` helper provided in test files:
```javascript
renderWithRouter(<Component />);
```

---

## Best Practices

### 1. Always Use screen Queries
```javascript
// ✓ Good
screen.getByText('Submit');

// ✗ Avoid
container.querySelector('button');
```

### 2. Query in Order of Preference
1. `getByRole()` — Most semantic
2. `getByLabelText()` — For form labels
3. `getByPlaceholderText()` — For placeholders
4. `getByText()` — For text content
5. `getByTestId()` — Last resort

### 3. Test User Behavior, Not Implementation
```javascript
// ✓ Good: Test what user sees
expect(screen.getByText('Error')).toBeInTheDocument();

// ✗ Avoid: Test internal state
expect(component.state.hasError).toBe(true);
```

### 4. Use async/await for User Actions
```javascript
// ✓ Good: User typing naturally
await userEvent.type(input, 'hello');

// ✗ Avoid: Direct manipulation
fireEvent.change(input, { target: { value: 'hello' } });
```

### 5. Keep Tests Focused
```javascript
// ✓ Good: One thing per test
test('shows error when password is wrong', () => { ... });
test('accepts correct password', () => { ... });

// ✗ Avoid: Multiple unrelated assertions
test('everything about login', () => { ... });
```

---

## Performance Optimization

### Run Only Changed Tests
```bash
npm test -- --onlyChanged
```

### Run Tests in Parallel
```bash
npm test -- --maxWorkers=4
```

### Exit After First Failure
```bash
npm test -- --bail
```

---

## Continuous Integration

### GitHub Actions

Create `.github/workflows/test.yml`:

```yaml
name: Component Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        node-version: [16.x, 18.x]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Use Node.js ${{ matrix.node-version }}
      uses: actions/setup-node@v3
      with:
        node-version: ${{ matrix.node-version }}
    
    - name: Install dependencies
      run: npm ci
    
    - name: Run tests
      run: npm test -- --coverage
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "Running component tests..."
npm test -- --onlyChanged --bail

if [ $? -ne 0 ]; then
  echo "Tests failed. Aborting commit."
  exit 1
fi
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Adding New Tests

### 1. Create Test File
```bash
touch src/components/NewComponent.test.js
```

### 2. Write Test Structure
```javascript
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import NewComponent from './NewComponent';

describe('NewComponent', () => {
  test('renders correctly', () => {
    render(<NewComponent />);
    expect(screen.getByText('Expected text')).toBeInTheDocument();
  });
});
```

### 3. Run Tests
```bash
npm test NewComponent.test.js
```

---

## Debugging

### Print Component HTML
```javascript
test('debugging', () => {
  const { debug } = render(<Component />);
  debug(); // Prints HTML to console
});
```

### Print Screen State
```javascript
test('debugging', () => {
  render(<Component />);
  screen.debug(); // Prints DOM
});
```

### Use Node Debugger
```bash
node --inspect-brk node_modules/.bin/jest --runInBand
```

---

## Additional Resources

### Documentation
- [React Testing Library Docs](https://testing-library.com/react)
- [Jest Documentation](https://jestjs.io/)
- [Vitest Documentation](https://vitest.dev/)

### Guides
- [React Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Testing Library Cheatsheet](https://testing-library.com/docs/queries/about)

### Tutorials
- [React Testing Tutorial](https://www.freecodecamp.org/news/react-testing-tutorial/)
- [Jest Testing Framework](https://www.freecodecamp.org/news/testing-react-hooks/)

---

## Verification Checklist

After setup, verify:

- [ ] Dependencies installed: `npm list react`
- [ ] Tests run successfully: `npm test`
- [ ] All 107 tests pass
- [ ] Execution time < 3 seconds
- [ ] No warnings or errors
- [ ] Coverage reports generate

---

## Next Steps

1. **Understand Tests:** Read [COMPONENT_TESTS_SUMMARY.md](COMPONENT_TESTS_SUMMARY.md)
2. **Learn Patterns:** Check [src/REACT_TESTING_GUIDE.md](src/REACT_TESTING_GUIDE.md)
3. **Run Tests:** `npm test`
4. **View Coverage:** `npm run test:coverage`
5. **Modify Tests:** Edit `.test.js` files as needed

---

## Summary

✅ Jest and Vitest fully configured
✅ 107 comprehensive component tests
✅ React Testing Library best practices
✅ Quick setup in 3 commands:
```bash
npm install
npm test
npm run test:coverage
```

Ready to test React components! 🚀
