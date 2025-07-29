/**
 * API Service for TikTrue Frontend
 * 
 * This service handles all API communications with the Django backend.
 * It provides a centralized way to make API calls with proper error handling,
 * authentication, and CORS configuration.
 */

import axios from 'axios';

// Configure axios defaults
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'https://api.tiktrue.com/api/v1';
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://api.tiktrue.com';

// Create axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds timeout
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
  withCredentials: true, // Enable CORS credentials
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and token refresh
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refreshToken');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
            refresh: refreshToken
          });

          const { access } = response.data;
          localStorage.setItem('token', access);
          
          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('token');
        localStorage.removeItem('refreshToken');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

/**
 * API Service Class
 * Provides methods for all API endpoints
 */
class ApiService {
  constructor() {
    this.client = apiClient;
    this.baseURL = API_BASE_URL;
    this.backendURL = BACKEND_URL;
  }

  // Authentication endpoints
  auth = {
    /**
     * Register a new user
     * @param {Object} userData - User registration data
     * @param {string} userData.email - User email
     * @param {string} userData.username - Username
     * @param {string} userData.password - Password
     * @param {string} userData.password_confirm - Password confirmation
     * @returns {Promise} API response
     */
    register: async (userData) => {
      try {
        const response = await this.client.post('/auth/register/', userData);
        
        // Store tokens if registration successful
        if (response.data.tokens) {
          localStorage.setItem('token', response.data.tokens.access);
          localStorage.setItem('refreshToken', response.data.tokens.refresh);
        }
        
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Login user
     * @param {Object} credentials - Login credentials
     * @param {string} credentials.email - User email
     * @param {string} credentials.password - Password
     * @param {string} credentials.hardware_fingerprint - Hardware fingerprint (optional)
     * @returns {Promise} API response
     */
    login: async (credentials) => {
      try {
        const response = await this.client.post('/auth/login/', credentials);
        
        // Store tokens if login successful
        if (response.data.tokens) {
          localStorage.setItem('token', response.data.tokens.access);
          localStorage.setItem('refreshToken', response.data.tokens.refresh);
        }
        
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Logout user
     * @returns {Promise} API response
     */
    logout: async () => {
      try {
        const refreshToken = localStorage.getItem('refreshToken');
        const response = await this.client.post('/auth/logout/', {
          refresh_token: refreshToken
        });
        
        // Clear stored tokens
        localStorage.removeItem('token');
        localStorage.removeItem('refreshToken');
        
        return response.data;
      } catch (error) {
        // Clear tokens even if logout request fails
        localStorage.removeItem('token');
        localStorage.removeItem('refreshToken');
        throw this.handleError(error);
      }
    },

    /**
     * Get user profile
     * @returns {Promise} User profile data
     */
    getProfile: async () => {
      try {
        const response = await this.client.get('/auth/profile/');
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Refresh access token
     * @returns {Promise} New tokens
     */
    refreshToken: async () => {
      try {
        const refreshToken = localStorage.getItem('refreshToken');
        const response = await this.client.post('/auth/refresh/', {
          refresh: refreshToken
        });
        
        localStorage.setItem('token', response.data.access);
        return response.data;
      } catch (error) {
        localStorage.removeItem('token');
        localStorage.removeItem('refreshToken');
        throw this.handleError(error);
      }
    }
  };

  // License endpoints
  license = {
    /**
     * Validate license key
     * @param {Object} licenseData - License validation data
     * @param {string} licenseData.license_key - License key
     * @param {string} licenseData.hardware_fingerprint - Hardware fingerprint
     * @returns {Promise} License validation response
     */
    validate: async (licenseData) => {
      try {
        const response = await this.client.post('/license/validate/', licenseData);
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Get license information
     * @returns {Promise} License information
     */
    getInfo: async () => {
      try {
        const response = await this.client.get('/license/info/');
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    }
  };

  // Model endpoints
  models = {
    /**
     * Get available models for user
     * @returns {Promise} Available models list
     */
    getAvailable: async () => {
      try {
        const response = await this.client.get('/models/available/');
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Get model metadata
     * @param {string} modelId - Model ID
     * @returns {Promise} Model metadata
     */
    getMetadata: async (modelId) => {
      try {
        const response = await this.client.get(`/models/${modelId}/metadata/`);
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Create download token for model
     * @param {string} modelId - Model ID
     * @returns {Promise} Download token
     */
    createDownloadToken: async (modelId) => {
      try {
        const response = await this.client.post(`/models/${modelId}/download/`);
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Download model using token
     * @param {string} downloadToken - Download token
     * @returns {Promise} Download response
     */
    downloadModel: async (downloadToken) => {
      try {
        const response = await this.client.get(`/models/download/${downloadToken}/`, {
          responseType: 'blob' // For file downloads
        });
        return response;
      } catch (error) {
        throw this.handleError(error);
      }
    }
  };

  // Desktop app download endpoints
  downloads = {
    /**
     * Get desktop app download information
     * @returns {Promise} Desktop app info and available versions
     */
    getDesktopAppInfo: async () => {
      try {
        const response = await this.client.get('/downloads/desktop-app-info/');
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Download desktop application
     * @param {string} filename - Desktop app filename
     * @returns {Promise} File download response
     */
    downloadDesktopApp: async (filename) => {
      try {
        const response = await this.client.get(`/downloads/desktop-app/${filename}`, {
          responseType: 'blob' // For file downloads
        });
        return response;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Get installation guide
     * @returns {Promise} Installation guide information
     */
    getInstallationGuide: async () => {
      try {
        const response = await this.client.get('/downloads/installation-guide/');
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    },

    /**
     * Trigger desktop app download with proper file handling
     * @param {string} filename - Desktop app filename
     * @param {string} displayName - Display name for download
     * @returns {Promise} Download result
     */
    triggerDesktopAppDownload: async (filename, displayName = null) => {
      try {
        const response = await this.downloadDesktopApp(filename);
        
        // Create blob URL and trigger download
        const blob = new Blob([response.data], { 
          type: response.headers['content-type'] || 'application/octet-stream' 
        });
        
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = displayName || filename;
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        
        // Cleanup
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        return { success: true, filename: displayName || filename };
      } catch (error) {
        throw this.handleError(error);
      }
    }
  };

  // Health and utility endpoints
  health = {
    /**
     * Check backend health
     * @returns {Promise} Health status
     */
    check: async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/health/`);
        return response.data;
      } catch (error) {
        throw this.handleError(error);
      }
    }
  };

  /**
   * Handle API errors consistently
   * @param {Error} error - Axios error object
   * @returns {Object} Formatted error object
   */
  handleError(error) {
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response;
      
      return {
        status,
        message: data.message || data.detail || 'An error occurred',
        errors: data.errors || data,
        isNetworkError: false
      };
    } else if (error.request) {
      // Network error
      return {
        status: 0,
        message: 'Network error - please check your connection',
        errors: {},
        isNetworkError: true
      };
    } else {
      // Other error
      return {
        status: 0,
        message: error.message || 'An unexpected error occurred',
        errors: {},
        isNetworkError: false
      };
    }
  }

  /**
   * Check if user is authenticated
   * @returns {boolean} Authentication status
   */
  isAuthenticated() {
    return !!localStorage.getItem('token');
  }

  /**
   * Get current auth token
   * @returns {string|null} Auth token
   */
  getAuthToken() {
    return localStorage.getItem('token');
  }

  /**
   * Set auth token
   * @param {string} token - Auth token
   */
  setAuthToken(token) {
    localStorage.setItem('token', token);
  }

  /**
   * Clear auth tokens
   */
  clearAuthTokens() {
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
  }
}

// Create and export singleton instance
const apiService = new ApiService();

export default apiService;

// Export individual services for convenience
export const { auth, license, models, downloads, health } = apiService;

// Export configuration for testing
export const config = {
  API_BASE_URL,
  BACKEND_URL,
  timeout: 30000
};