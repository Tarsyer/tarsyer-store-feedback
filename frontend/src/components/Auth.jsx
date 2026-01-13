import React, { useState } from 'react';
import './Auth.css';

function Auth({ onLogin, userType }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();

    // Simple password check (in production, this should be server-side)
    const correctPassword = userType === 'staff'
      ? import.meta.env.VITE_STAFF_PASSWORD || 'staff123'
      : import.meta.env.VITE_MANAGER_PASSWORD || 'manager123';

    if (password === correctPassword) {
      onLogin(true);
      localStorage.setItem(`${userType}_auth`, 'true');
    } else {
      setError('Incorrect password');
      setPassword('');
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/Tarsyer_Logo.png" alt="Tarsyer Store Sentiment" className="auth-logo" />
        <h1>Tarsyer Store Sentiment</h1>
        <h2>{userType === 'staff' ? 'Staff Login' : 'Manager Dashboard Login'}</h2>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError('');
              }}
              placeholder="Enter password"
              autoFocus
              required
            />
          </div>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-submit">
            Login
          </button>
        </form>

        <p className="auth-help">
          {userType === 'staff'
            ? 'For staff members to upload feedback recordings'
            : 'For managers to view analytics and reports'}
        </p>
      </div>
    </div>
  );
}

export default Auth;
