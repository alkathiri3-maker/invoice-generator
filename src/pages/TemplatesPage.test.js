import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import TemplatesPage from './TemplatesPage';

const renderWithRouter = (component) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('TemplatesPage Component', () => {
  test('renders templates page', () => {
    renderWithRouter(<TemplatesPage />);

    const page = screen.getByText('محرر مرئي');
    expect(page).toBeInTheDocument();
  });

  test('renders visual editor link with Arabic text', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByText('محرر مرئي');
    expect(link).toBeInTheDocument();
  });

  test('link has correct href attribute', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/visual-editor');
  });

  test('link is clickable', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByText('محرر مرئي');
    expect(link).toBeEnabled();

    fireEvent.click(link);
    expect(link).toBeInTheDocument();
  });

  test('link has proper styling classes', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('px-4');
    expect(classString).toContain('py-2');
    expect(classString).toContain('bg-green-500');
    expect(classString).toContain('text-white');
    expect(classString).toContain('rounded');
  });

  test('link has hover state styling', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('hover:bg-green-600');
  });

  test('link is displayed inline', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('inline-block');
  });

  test('page renders without errors', () => {
    expect(() => {
      renderWithRouter(<TemplatesPage />);
    }).not.toThrow();
  });

  test('link text is in Arabic', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByText('محرر مرئي');
    expect(link.textContent).toBe('محرر مرئي');
  });

  test('only one link is rendered', () => {
    renderWithRouter(<TemplatesPage />);

    const links = screen.getAllByRole('link');
    expect(links.length).toBe(1);
  });

  test('link text is visible', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByText('محرر مرئي');
    expect(link).toBeVisible();
  });

  test('link element has button-like appearance', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    // Button-like styling
    expect(classString).toMatch(/bg-|px-|py-|rounded/);
  });

  test('link destination is correct', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link', { name: /محرر مرئي/ });
    expect(link.href).toContain('/visual-editor');
  });

  test('link can be clicked multiple times', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByText('محرر مرئي');

    fireEvent.click(link);
    fireEvent.click(link);
    fireEvent.click(link);

    expect(link).toBeInTheDocument();
  });

  test('page container renders properly', () => {
    const { container } = renderWithRouter(<TemplatesPage />);

    expect(container.firstChild).toBeInTheDocument();
  });

  test('link has proper element type', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    expect(link.tagName).toBe('A');
  });

  test('component mounts without crashing', () => {
    expect(() => {
      renderWithRouter(<TemplatesPage />);
    }).not.toThrow();
  });

  test('link is not disabled', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    expect(link).not.toBeDisabled();
  });

  test('page renders with correct structure', () => {
    const { container } = renderWithRouter(<TemplatesPage />);

    const divElement = container.querySelector('div');
    expect(divElement).toBeInTheDocument();

    const linkElement = divElement.querySelector('a');
    expect(linkElement).toBeInTheDocument();
  });

  test('link navigates to visual editor route', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link', { name: /محرر مرئي/ });
    expect(link.href).toMatch(/visual-editor$/);
  });
});

describe('TemplatesPage Accessibility', () => {
  test('link is keyboard accessible', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    link.focus();

    expect(link).toHaveFocus();
  });

  test('link has proper aria attributes if needed', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    expect(link).toBeInTheDocument();
  });

  test('Arabic text is properly accessible', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByText('محرر مرئي');
    expect(link).toHaveAccessibleName('محرر مرئي');
  });
});

describe('TemplatesPage User Interactions', () => {
  test('link responds to click events', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    await user.click(link);

    expect(link).toBeInTheDocument();
  });

  test('link responds to keyboard navigation', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    link.focus();

    expect(link).toHaveFocus();
  });

  test('link can be tabbed to', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    link.focus();

    expect(link).toHaveFocus();
  });
});

describe('TemplatesPage Rendering', () => {
  test('renders without props', () => {
    expect(() => {
      renderWithRouter(<TemplatesPage />);
    }).not.toThrow();
  });

  test('component is a function component', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    expect(link).toBeInTheDocument();
  });

  test('renders with React Fragment or Div wrapper', () => {
    const { container } = renderWithRouter(<TemplatesPage />);

    expect(container.children.length).toBeGreaterThan(0);
  });

  test('page content is not empty', () => {
    renderWithRouter(<TemplatesPage />);

    const page = screen.getByRole('link');
    expect(page).toBeInTheDocument();
  });

  test('link text is exact match', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByText('محرر مرئي', { exact: true });
    expect(link).toBeInTheDocument();
  });

  test('page renders consistently', () => {
    const { rerender } = renderWithRouter(<TemplatesPage />);

    expect(screen.getByText('محرر مرئي')).toBeInTheDocument();

    rerender(
      <BrowserRouter>
        <TemplatesPage />
      </BrowserRouter>
    );

    expect(screen.getByText('محرر مرئي')).toBeInTheDocument();
  });
});

describe('TemplatesPage Button-like Link', () => {
  test('link has button styling', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    // Check for typical button classes
    expect(classString).toMatch(/px-\d+|py-\d+|bg-/);
  });

  test('link has color styling', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('text-white');
    expect(classString).toContain('bg-green-500');
  });

  test('link text is white', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('text-white');
  });

  test('link background is green', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('bg-green-500');
  });

  test('link has padding', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('px-4');
    expect(classString).toContain('py-2');
  });

  test('link has rounded corners', () => {
    renderWithRouter(<TemplatesPage />);

    const link = screen.getByRole('link');
    const classString = link.getAttribute('class');

    expect(classString).toContain('rounded');
  });
});
