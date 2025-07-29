import React, { createContext, useContext, useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import apiService from '../services/apiService';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('token'));

  // Check if user is authenticated on app load
  useEffect(() => {
    const checkAuth = async () => {
      if (token) {
        try {
          const userData = await apiService.auth.getProfile();
          setUser(userData);
        } catch (error) {
          console.error('Auth check failed:', error);
          logout();
        }
      }
      setLoading(false);
    };

    checkAuth();
  }, [token]);

  const login = async (email, password, hardwareFingerprint = 'web-browser') => {
    try {
      const response = await apiService.auth.login({
        email,
        password,
        hardware_fingerprint: hardwareFingerprint
      });

      const { user: userData } = response;
      
      setUser(userData);
      setToken(apiService.getAuthToken());
      
      toast.success('Login successful!');
      return { success: true };
    } catch (error) {
      const message = error.message || 'Login failed';
      toast.error(message);
      return { success: false, error: message };
    }
  };

  const register = async (email, username, password, passwordConfirm) => {
    try {
      const response = await apiService.auth.register({
        email,
        username,
        password,
        password_confirm: passwordConfirm
      });

      const { user: userData } = response;
      
      setUser(userData);
      setToken(apiService.getAuthToken());
      
      toast.success('Registration successful!');
      return { success: true };
    } catch (error) {
      const message = error.message || 'Registration failed';
      toast.error(message);
      return { success: false, error: message };
    }
  };

  const logout = async () => {
    try {
      await apiService.auth.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setToken(null);
      toast.success('Logged out successfully');
    }
  };

  const forgotPassword = async (email) => {
    try {
      // Note: This endpoint may not be implemented yet
      await apiService.client.post('/auth/forgot-password/', { email });
      toast.success('Password reset email sent!');
      return { success: true };
    } catch (error) {
      const message = error.message || 'Failed to send reset email';
      toast.error(message);
      return { success: false, error: message };
    }
  };

  const resetPassword = async (token, password, passwordConfirm) => {
    try {
      // Note: This endpoint may not be implemented yet
      await apiService.client.post('/auth/reset-password/', {
        token,
        password,
        password_confirm: passwordConfirm
      });
      toast.success('Password reset successful!');
      return { success: true };
    } catch (error) {
      const message = error.message || 'Password reset failed';
      toast.error(message);
      return { success: false, error: message };
    }
  };

  const value = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    forgotPassword,
    resetPassword,
    isAuthenticated: !!user
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};