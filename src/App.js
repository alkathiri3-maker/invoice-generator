import React, { useState } from 'react';
import { BrowserRouter as Router, Route, Routes, Link, Navigate } from 'react-router-dom';
import './style.css';

// Simulated password storage (replace with localStorage or backend)
const PASSWORD_STORAGE = {
  admin: 'admin@123',
  trainee: null // Will be set by admin
};

const LoginPage = ({ setPassword }) => {
  const [role, setRole] = useState(null);
  const [inputPassword, setInputPassword] = useState('');
  const [error, setError] = useState('');

  const handlePasswordSubmit = () => {
    const storedPassword = PASSWORD_STORAGE[role];
    if (!storedPassword || inputPassword !== storedPassword) {
      setError('Incorrect password');
      return;
    }
    setPassword(inputPassword);
  };

  return (
    <div className="login-container">
      <h1>Login</h1>
      {!role ? (
        <div className="login-options">
          <button onClick={() => setRole('admin')} className="login-option admin">
            <h2>Admin/Supervisor</h2>
          </button>
          <button onClick={() => setRole('trainee')} className="login-option trainee">
            <h2>Trainee/Student</h2>
          </button>
        </div>
      ) : (
        <div className="password-entry">
          <h2>Enter {role} Password</h2>
          <input
            type="password"
            value={inputPassword}
            onChange={(e) => setInputPassword(e.target.value)}
            placeholder="Enter password"
          />
          <button onClick={handlePasswordSubmit}>Submit</button>
          {error && <p className="error">{error}</p>}
        </div>
      )}
    </div>
  );
};

const AdminDashboard = ({ password, setTraineePassword }) => {
  const [newPassword, setNewPassword] = useState('');

  const handleSetTraineePassword = () => {
    PASSWORD_STORAGE.trainee = newPassword;
    setNewPassword('');
  };

  return (
    <div className="dashboard">
      <h1>Admin Dashboard</h1>
      <div className="password-control">
        <h2>Set Trainee Password</h2>
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="New trainee password"
        />
        <button onClick={handleSetTraineePassword}>Set Password</button>
      </div>
    </div>
  );
};

const TraineeView = ({ password }) => {
  return (
    <div className="dashboard">
      <h1>Trainee View</h1>
      <p>Logged in with password: {password}</p>
    </div>
  );
};

function App() {
  const [password, setPassword] = useState(null);

  return (
    <Router>
      <Routes>
        <Route path="/" element={<LoginPage setPassword={setPassword} />} />
        <Route path="/admin-dashboard" element={password ? <AdminDashboard password={password} /> : <Navigate to="/" />} />
        <Route path="/trainee-view" element={password ? <TraineeView password={password} /> : <Navigate to="/" />} />
      </Routes>
    </Router>
  );
}

export default App;