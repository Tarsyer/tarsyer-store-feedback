import React, { useState } from 'react';
import './Auth.css';

const API_BASE = import.meta.env.VITE_API_URL || 'https://store-feedback.tarsyer.com';

function AuthJWT({ onLogin, userType }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Call JWT authentication API
      const response = await fetch(`${API_BASE}/api/v1/auth/login/json`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Authentication failed');
      }

      const data = await response.json();

      // Verify user role matches expected type
      // Decode JWT to check role (basic client-side validation)
      const tokenPayload = JSON.parse(atob(data.access_token.split('.')[1]));
      const userRole = tokenPayload.role;

      // For manager dashboard, require manager or admin role
      if (userType === 'manager' && !['manager', 'admin'].includes(userRole)) {
        throw new Error('Access denied. Manager or Admin role required.');
      }

      // Store JWT token securely
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('user_role', userRole);
      localStorage.setItem('username', tokenPayload.sub);
      localStorage.setItem('user_name', tokenPayload.name || '');

      // Set token expiration time (from JWT exp claim)
      if (tokenPayload.exp) {
        localStorage.setItem('token_expiry', tokenPayload.exp.toString());
      }

      onLogin(true);
    } catch (err) {
      console.error('Login error:', err);
      setError(err.message || 'Login failed. Please check your credentials.');
      setPassword('');
    } finally {
      setLoading(false);
    }
  };

  // Check if user should use username or default staff login
  const isManagerLogin = userType === 'manager';

  return (
    <div className="auth-container">
      <div className="auth-card">
        <img src="/Tarsyer_Logo.png" alt="Tarsyer Store Sentiment" className="auth-logo" />
        <h1>Tarsyer Store Sentiment</h1>
        <h2>{isManagerLogin ? 'Manager Dashboard Login' : 'Staff Login'}</h2>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                setError('');
              }}
              placeholder="Enter your username"
              autoFocus
              required
              disabled={loading}
            />
          </div>

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
              placeholder="Enter your password"
              required
              disabled={loading}
            />
          </div>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className="auth-help">
          {isManagerLogin
            ? 'For managers to view analytics and reports'
            : 'For staff members to upload feedback recordings'}
        </p>
      </div>
    </div>
  );
}

export default AuthJWT;
