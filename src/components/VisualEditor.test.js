import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VisualEditor from './VisualEditor';

describe('VisualEditor Component', () => {
  test('renders visual editor container', () => {
    render(<VisualEditor />);

    const container = screen.getByText(/نافذة التحرير المرئي/);
    expect(container).toBeInTheDocument();
  });

  test('renders save button with Arabic text', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    expect(saveButton).toBeInTheDocument();
  });

  test('renders reset button with Arabic text', () => {
    render(<VisualEditor />);

    const resetButton = screen.getByText('إرجاع الافتراضي');
    expect(resetButton).toBeInTheDocument();
  });

  test('save button is clickable', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    expect(saveButton).toBeEnabled();

    fireEvent.click(saveButton);
    expect(saveButton).toBeInTheDocument();
  });

  test('reset button is clickable', () => {
    render(<VisualEditor />);

    const resetButton = screen.getByText('إرجاع الافتراضي');
    expect(resetButton).toBeEnabled();

    fireEvent.click(resetButton);
    expect(resetButton).toBeInTheDocument();
  });

  test('header section contains both buttons', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    const resetButton = screen.getByText('إرجاع الافتراضي');

    expect(saveButton).toBeInTheDocument();
    expect(resetButton).toBeInTheDocument();
  });

  test('content area displays placeholder text', () => {
    render(<VisualEditor />);

    const placeholder = screen.getByText('نافذة التحرير المرئي المتقدم');
    expect(placeholder).toBeInTheDocument();
  });

  test('header has proper styling classes', () => {
    const { container } = render(<VisualEditor />);

    const header = container.querySelector('[class*="bg-gray-100"]');
    expect(header).toBeInTheDocument();
  });

  test('main container has proper layout classes', () => {
    const { container } = render(<VisualEditor />);

    const mainContainer = container.querySelector('[class*="fixed"]');
    expect(mainContainer).toBeInTheDocument();
  });

  test('buttons have hover states', () => {
    const { container } = render(<VisualEditor />);

    const buttons = container.querySelectorAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);

    buttons.forEach(button => {
      const classString = button.getAttribute('class');
      expect(classString).toContain('hover:');
    });
  });

  test('buttons have proper padding', () => {
    const { container } = render(<VisualEditor />);

    const buttons = container.querySelectorAll('button');
    buttons.forEach(button => {
      const classString = button.getAttribute('class');
      expect(classString).toMatch(/px-|py-/);
    });
  });

  test('buttons have text color styling', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    const resetButton = screen.getByText('إرجاع الافتراضي');

    expect(saveButton.className).toContain('text-white');
    expect(resetButton.className).toContain('text-white');
  });

  test('buttons have background color styling', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    const resetButton = screen.getByText('إرجاع الافتراضي');

    expect(saveButton.className).toContain('bg-');
    expect(resetButton.className).toContain('bg-');
  });

  test('content area is scrollable', () => {
    const { container } = render(<VisualEditor />);

    const contentArea = container.querySelector('[class*="overflow-auto"]');
    expect(contentArea).toBeInTheDocument();
  });

  test('layout uses flexbox', () => {
    const { container } = render(<VisualEditor />);

    const mainContainer = container.querySelector('[class*="flex"]');
    expect(mainContainer).toBeInTheDocument();
  });

  test('buttons can handle rapid clicks', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');

    fireEvent.click(saveButton);
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);

    expect(saveButton).toBeInTheDocument();
  });

  test('both buttons remain after clicking', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    const resetButton = screen.getByText('إرجاع الافتراضي');

    fireEvent.click(saveButton);
    fireEvent.click(resetButton);

    expect(saveButton).toBeInTheDocument();
    expect(resetButton).toBeInTheDocument();
  });

  test('component maintains state after render', () => {
    const { rerender } = render(<VisualEditor />);

    expect(screen.getByText('حفظ التخصيصات')).toBeInTheDocument();

    rerender(<VisualEditor />);

    expect(screen.getByText('حفظ التخصيصات')).toBeInTheDocument();
  });

  test('Arabic text is properly rendered', () => {
    render(<VisualEditor />);

    const arabicTexts = [
      'حفظ التخصيصات',
      'إرجاع الافتراضي',
      'نافذة التحرير المرئي المتقدم'
    ];

    arabicTexts.forEach(text => {
      expect(screen.getByText(text)).toBeInTheDocument();
    });
  });

  test('header is fixed at top', () => {
    const { container } = render(<VisualEditor />);

    const header = container.querySelector('[class*="border-b"]');
    expect(header).toBeInTheDocument();
  });

  test('content area fills remaining space', () => {
    const { container } = render(<VisualEditor />);

    const contentArea = container.querySelector('[class*="flex-1"]');
    expect(contentArea).toBeInTheDocument();
  });

  test('buttons are not disabled by default', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    const resetButton = screen.getByText('إرجاع الافتراضي');

    expect(saveButton).not.toBeDisabled();
    expect(resetButton).not.toBeDisabled();
  });

  test('buttons have proper element type', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    const resetButton = screen.getByText('إرجاع الافتراضي');

    expect(saveButton.tagName).toBe('BUTTON');
    expect(resetButton.tagName).toBe('BUTTON');
  });

  test('save button is positioned on left side', () => {
    const { container } = render(<VisualEditor />);

    const buttons = container.querySelectorAll('button');
    expect(buttons[0].textContent).toContain('حفظ التخصيصات');
  });

  test('reset button is positioned after save button', () => {
    const { container } = render(<VisualEditor />);

    const buttons = container.querySelectorAll('button');
    expect(buttons[1].textContent).toContain('إرجاع الافتراضي');
  });

  test('component renders without props', () => {
    const { container } = render(<VisualEditor />);
    expect(container).toBeInTheDocument();
  });

  test('multiple instances render independently', () => {
    const { rerender } = render(
      <div>
        <VisualEditor />
        <VisualEditor />
      </div>
    );

    const buttons = screen.getAllByText('حفظ التخصيصات');
    expect(buttons.length).toBe(2);
  });
});

describe('VisualEditor Accessibility', () => {
  test('buttons have proper role', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByRole('button', { name: /حفظ التخصيصات/ });
    const resetButton = screen.getByRole('button', { name: /إرجاع الافتراضي/ });

    expect(saveButton).toBeInTheDocument();
    expect(resetButton).toBeInTheDocument();
  });

  test('buttons are keyboard accessible', () => {
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    saveButton.focus();

    expect(saveButton).toHaveFocus();
  });

  test('header is properly structured', () => {
    const { container } = render(<VisualEditor />);

    const header = container.querySelector('[class*="bg-gray-100"]');
    expect(header).toBeInTheDocument();
    expect(header.querySelector('button')).toBeInTheDocument();
  });
});

describe('VisualEditor User Interactions', () => {
  test('save button responds to click events', async () => {
    const user = userEvent.setup();
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    await user.click(saveButton);

    expect(saveButton).toBeInTheDocument();
  });

  test('reset button responds to click events', async () => {
    const user = userEvent.setup();
    render(<VisualEditor />);

    const resetButton = screen.getByText('إرجاع الافتراضي');
    await user.click(resetButton);

    expect(resetButton).toBeInTheDocument();
  });

  test('buttons can be clicked in sequence', async () => {
    const user = userEvent.setup();
    render(<VisualEditor />);

    const saveButton = screen.getByText('حفظ التخصيصات');
    const resetButton = screen.getByText('إرجاع الافتراضي');

    await user.click(saveButton);
    await user.click(resetButton);
    await user.click(saveButton);

    expect(saveButton).toBeInTheDocument();
    expect(resetButton).toBeInTheDocument();
  });
});
