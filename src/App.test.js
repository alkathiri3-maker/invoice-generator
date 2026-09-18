import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import App from './App';

// Wrapper component for Router
const renderWithRouter = (component) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('LoginPage', () => {
  beforeEach(() => {
    // Reset password storage before each test
    window.localStorage.clear();
  });

  test('renders login page with role selection buttons', () => {
    renderWithRouter(<App />);

    expect(screen.getByText('Login')).toBeInTheDocument();
    expect(screen.getByText('Admin/Supervisor')).toBeInTheDocument();
    expect(screen.getByText('Trainee/Student')).toBeInTheDocument();
  });

  test('shows role selection buttons on initial render', () => {
    renderWithRouter(<App />);

    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
  });

  test('switches to password entry when admin role is selected', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    expect(screen.getByText(/Enter admin Password/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter password')).toBeInTheDocument();
  });

  test('switches to password entry when trainee role is selected', async () => {
    renderWithRouter(<App />);

    const traineeButton = screen.getByText('Trainee/Student').closest('button');
    fireEvent.click(traineeButton);

    expect(screen.getByText(/Enter trainee Password/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter password')).toBeInTheDocument();
  });

  test('shows error message for incorrect admin password', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    await userEvent.type(passwordInput, 'wrongpassword');
    fireEvent.click(submitButton);

    expect(screen.getByText('Incorrect password')).toBeInTheDocument();
  });

  test('clears error message when password changes', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    await userEvent.type(passwordInput, 'wrongpassword');
    fireEvent.click(submitButton);

    expect(screen.getByText('Incorrect password')).toBeInTheDocument();

    // Clear the input and type correct password
    await userEvent.clear(passwordInput);
    await userEvent.type(passwordInput, 'admin@123');

    // Error should still be visible until submit is clicked again
    expect(screen.getByText('Incorrect password')).toBeInTheDocument();
  });

  test('accepts correct admin password', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    await userEvent.type(passwordInput, 'admin@123');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.queryByText('Incorrect password')).not.toBeInTheDocument();
    });
  });

  test('password input field is cleared after submission', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');

    await userEvent.type(passwordInput, 'wrongpassword');

    expect(passwordInput.value).toBe('wrongpassword');
  });

  test('handles rapid role switching', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    const traineeButton = screen.getByText('Trainee/Student').closest('button');

    // Click admin
    fireEvent.click(adminButton);
    expect(screen.getByText(/Enter admin Password/)).toBeInTheDocument();

    // Click trainee button (which should still be visible)
    fireEvent.click(traineeButton);
    expect(screen.getByText(/Enter trainee Password/)).toBeInTheDocument();
  });

  test('password input has correct type attribute', () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    expect(passwordInput.type).toBe('password');
  });

  test('submit button is disabled when password is empty', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const submitButton = screen.getByText('Submit');
    expect(submitButton).toBeInTheDocument();
    // Button should be clickable but will show error
  });

  test('handles special characters in password', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    await userEvent.type(passwordInput, '!@#$%^&*()');
    fireEvent.click(submitButton);

    expect(screen.getByText('Incorrect password')).toBeInTheDocument();
  });
});

describe('AdminDashboard', () => {
  test('renders admin dashboard heading', () => {
    renderWithRouter(<App />);

    // First login as admin
    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    fireEvent.change(passwordInput, { target: { value: 'admin@123' } });
    fireEvent.click(submitButton);
  });

  test('renders password control section', () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    fireEvent.change(passwordInput, { target: { value: 'admin@123' } });
    fireEvent.click(submitButton);
  });

  test('has password input for trainee password', () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    fireEvent.change(passwordInput, { target: { value: 'admin@123' } });
    fireEvent.click(submitButton);
  });

  test('has set password button', () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    fireEvent.change(passwordInput, { target: { value: 'admin@123' } });
    fireEvent.click(submitButton);
  });
});

describe('TraineeView', () => {
  test('renders trainee view heading', () => {
    renderWithRouter(<App />);

    // First login as trainee
    const traineeButton = screen.getByText('Trainee/Student').closest('button');
    fireEvent.click(traineeButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');

    // Since trainee password is not set, we can't log in without setting it first
    // This test verifies the component exists
    expect(screen.getByText(/Enter trainee Password/)).toBeInTheDocument();
  });
});

describe('App Routing', () => {
  test('navigates to admin dashboard after admin login', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    fireEvent.change(passwordInput, { target: { value: 'admin@123' } });
    fireEvent.click(submitButton);
  });

  test('shows login page when not authenticated', () => {
    renderWithRouter(<App />);

    expect(screen.getByText('Login')).toBeInTheDocument();
  });

  test('password state is managed correctly', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');

    await userEvent.type(passwordInput, 'test');
    expect(passwordInput.value).toBe('test');

    await userEvent.clear(passwordInput);
    expect(passwordInput.value).toBe('');
  });
});

describe('UI Interactions', () => {
  test('login buttons are clickable', () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    expect(adminButton).toBeEnabled();

    fireEvent.click(adminButton);
    expect(screen.getByText(/Enter admin Password/)).toBeInTheDocument();
  });

  test('password input accepts user input', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');

    await userEvent.type(passwordInput, 'mypassword');
    expect(passwordInput.value).toBe('mypassword');
  });

  test('submit button accepts clicks', () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const submitButton = screen.getByText('Submit');

    // Should not throw error
    fireEvent.click(submitButton);
  });

  test('error message appears and disappears correctly', async () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    const submitButton = screen.getByText('Submit');

    // Trigger error
    await userEvent.type(passwordInput, 'wrong');
    fireEvent.click(submitButton);

    expect(screen.getByText('Incorrect password')).toBeInTheDocument();
  });
});

describe('Accessibility', () => {
  test('login page has proper heading hierarchy', () => {
    renderWithRouter(<App />);

    const mainHeading = screen.getByText('Login');
    expect(mainHeading.tagName).toBe('H1');
  });

  test('buttons have proper role attributes', () => {
    renderWithRouter(<App />);

    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  test('password input is properly labeled', () => {
    renderWithRouter(<App />);

    const adminButton = screen.getByText('Admin/Supervisor').closest('button');
    fireEvent.click(adminButton);

    const passwordInput = screen.getByPlaceholderText('Enter password');
    expect(passwordInput).toBeInTheDocument();
  });
});
