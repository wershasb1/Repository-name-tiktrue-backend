import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Download, 
  Shield, 
  Clock, 
  Users, 
  Activity,
  Settings,
  CreditCard,
  FileText,
  AlertCircle,
  CheckCircle,
  ExternalLink
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/apiService';
import toast from 'react-hot-toast';

const DashboardPage = () => {
  const { user } = useAuth();
  const [models, setModels] = useState([]);
  const [license, setLicense] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
    fetchDownloadInfo();
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Fetch available models
      const modelsData = await apiService.models.getAvailable();
      setModels(modelsData.models || []);

      // Fetch license info
      const licenseData = await apiService.license.getInfo();
      setLicense(licenseData.license || null);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const [downloadInfo, setDownloadInfo] = useState(null);
  const [downloadLoading, setDownloadLoading] = useState(false);

  const fetchDownloadInfo = async () => {
    try {
      const info = await apiService.downloads.getDesktopAppInfo();
      setDownloadInfo(info);
    } catch (error) {
      console.error('Failed to fetch download info:', error);
      // Don't show error toast here as it might be due to subscription plan
    }
  };

  const handleDownloadApp = async (filename = 'TikTrue_Real_Build.exe', displayName = 'TikTrue-Desktop-App.exe') => {
    if (downloadLoading) return;
    
    setDownloadLoading(true);
    
    try {
      await apiService.downloads.triggerDesktopAppDownload(filename, displayName);
      toast.success('Download started successfully!');
    } catch (error) {
      console.error('Download failed:', error);
      
      if (error.status === 403) {
        toast.error('Desktop app download requires Pro or Enterprise subscription');
      } else if (error.status === 404) {
        toast.error('Download file not available');
      } else {
        toast.error('Download failed. Please try again later.');
      }
    } finally {
      setDownloadLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-900 pt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Welcome back, {user?.username || user?.email}!
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Manage your TikTrue AI platform and access your distributed models.
          </p>
        </motion.div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="card p-6"
          >
            <div className="flex items-center">
              <div className="p-2 bg-primary-100 dark:bg-primary-900 rounded-lg">
                <Shield className="w-6 h-6 text-primary-600 dark:text-primary-400" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Plan</p>
                <p className="text-2xl font-semibold text-gray-900 dark:text-white capitalize">
                  {user?.subscription_plan}
                </p>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="card p-6"
          >
            <div className="flex items-center">
              <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
                <Users className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Max Clients</p>
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {user?.max_clients}
                </p>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="card p-6"
          >
            <div className="flex items-center">
              <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                <Activity className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Models</p>
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {models.length}
                </p>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="card p-6"
          >
            <div className="flex items-center">
              <div className="p-2 bg-purple-100 dark:bg-purple-900 rounded-lg">
                <Clock className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Member Since</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {formatDate(user?.created_at)}
                </p>
              </div>
            </div>
          </motion.div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-8">
            {/* Download Section */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.5 }}
              className="card p-6"
            >
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                Desktop Application
              </h2>
              
              {downloadInfo && downloadInfo.download_access ? (
                <div className="space-y-4">
                  <div className="bg-gradient-to-r from-primary-50 to-purple-50 dark:from-primary-900/20 dark:to-purple-900/20 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                          TikTrue Desktop App
                        </h3>
                        <p className="text-gray-600 dark:text-gray-400 mt-1">
                          Download the desktop application to start using distributed AI models
                        </p>
                        <div className="flex items-center mt-2 text-sm text-gray-500 dark:text-gray-400">
                          <CheckCircle className="w-4 h-4 mr-1 text-green-500" />
                          Your plan: {downloadInfo.user_plan} • Download access enabled
                        </div>
                      </div>
                    </div>
                    
                    {/* Available Versions */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {downloadInfo.available_versions?.map((version, index) => (
                        <div key={index} className="bg-white dark:bg-dark-800 rounded-lg p-4 border border-gray-200 dark:border-dark-600">
                          <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-2">
                            {version.name}
                          </h4>
                          <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
                            {version.description}
                          </p>
                          <div className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                            <div>Size: {version.size_mb} MB</div>
                            <div>Version: {version.version}</div>
                          </div>
                          <button
                            onClick={() => handleDownloadApp(version.filename, version.name)}
                            disabled={downloadLoading}
                            className="w-full btn-primary text-xs py-2 flex items-center justify-center gap-1 disabled:opacity-50"
                          >
                            {downloadLoading ? (
                              <>
                                <div className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin"></div>
                                Downloading...
                              </>
                            ) : (
                              <>
                                <Download className="w-3 h-3" />
                                Download
                              </>
                            )}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  {/* Installation Guide Link */}
                  <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium text-blue-900 dark:text-blue-100">
                          Need help with installation?
                        </h4>
                        <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                          Check our step-by-step installation guide
                        </p>
                      </div>
                      <button
                        onClick={() => window.open('/api/v1/downloads/installation-guide/', '_blank')}
                        className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 flex items-center gap-1 text-sm"
                      >
                        <FileText className="w-4 h-4" />
                        View Guide
                      </button>
                    </div>
                  </div>
                </div>
              ) : downloadInfo && !downloadInfo.download_access ? (
                <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-6">
                  <div className="flex items-center">
                    <AlertCircle className="w-8 h-8 text-yellow-500 mr-4" />
                    <div>
                      <h3 className="text-lg font-medium text-yellow-900 dark:text-yellow-100">
                        Upgrade Required
                      </h3>
                      <p className="text-yellow-700 dark:text-yellow-300 mt-1">
                        Desktop app download requires Pro or Enterprise subscription
                      </p>
                      <p className="text-sm text-yellow-600 dark:text-yellow-400 mt-2">
                        Current plan: {user?.subscription_plan}
                      </p>
                      <button className="mt-3 bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-2">
                        <CreditCard className="w-4 h-4" />
                        Upgrade Plan
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-gradient-to-r from-primary-50 to-purple-50 dark:from-primary-900/20 dark:to-purple-900/20 rounded-lg p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                        TikTrue Desktop App
                      </h3>
                      <p className="text-gray-600 dark:text-gray-400 mt-1">
                        Download the desktop application to start using distributed AI models
                      </p>
                      <div className="flex items-center mt-2 text-sm text-gray-500 dark:text-gray-400">
                        <CheckCircle className="w-4 h-4 mr-1 text-green-500" />
                        Version 1.0.0 • Windows 10/11
                      </div>
                    </div>
                    <button
                      onClick={() => handleDownloadApp()}
                      disabled={downloadLoading}
                      className="btn-primary flex items-center gap-2 disabled:opacity-50"
                    >
                      {downloadLoading ? (
                        <>
                          <div className="w-4 h-4 border border-white border-t-transparent rounded-full animate-spin"></div>
                          Downloading...
                        </>
                      ) : (
                        <>
                          <Download className="w-5 h-5" />
                          Download
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </motion.div>

            {/* Available Models */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.6 }}
              className="card p-6"
            >
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                Available Models
              </h2>
              <div className="space-y-4">
                {models.map((model, index) => (
                  <div key={index} className="border border-gray-200 dark:border-dark-600 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900 dark:text-white">
                          {model.display_name}
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {model.description}
                        </p>
                        <div className="flex items-center mt-2 text-xs text-gray-500 dark:text-gray-400">
                          <span>Version {model.version}</span>
                          <span className="mx-2">•</span>
                          <span>{(model.file_size / 1000000000).toFixed(1)} GB</span>
                          <span className="mx-2">•</span>
                          <span>{model.block_count} blocks</span>
                        </div>
                      </div>
                      <div className="flex items-center">
                        <CheckCircle className="w-5 h-5 text-green-500" />
                        <span className="ml-2 text-sm text-green-600 dark:text-green-400">
                          Available
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* License Info */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.7 }}
              className="card p-6"
            >
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                License Information
              </h3>
              {license ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Status</span>
                    <span className="flex items-center text-sm text-green-600 dark:text-green-400">
                      <CheckCircle className="w-4 h-4 mr-1" />
                      Active
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">License Key</span>
                    <span className="text-sm font-mono text-gray-900 dark:text-white">
                      {license.license_key.substring(0, 16)}...
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Created</span>
                    <span className="text-sm text-gray-900 dark:text-white">
                      {formatDate(license.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Usage Count</span>
                    <span className="text-sm text-gray-900 dark:text-white">
                      {license.usage_count}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4">
                  <AlertCircle className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    No license information available
                  </p>
                </div>
              )}
            </motion.div>

            {/* Quick Actions */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.8 }}
              className="card p-6"
            >
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Quick Actions
              </h3>
              <div className="space-y-3">
                <button className="w-full flex items-center justify-between p-3 text-left bg-gray-50 dark:bg-dark-700 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors duration-200">
                  <div className="flex items-center">
                    <Settings className="w-5 h-5 text-gray-600 dark:text-gray-400 mr-3" />
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      Account Settings
                    </span>
                  </div>
                  <ExternalLink className="w-4 h-4 text-gray-400" />
                </button>

                <button className="w-full flex items-center justify-between p-3 text-left bg-gray-50 dark:bg-dark-700 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors duration-200">
                  <div className="flex items-center">
                    <CreditCard className="w-5 h-5 text-gray-600 dark:text-gray-400 mr-3" />
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      Billing & Plans
                    </span>
                  </div>
                  <ExternalLink className="w-4 h-4 text-gray-400" />
                </button>

                <button className="w-full flex items-center justify-between p-3 text-left bg-gray-50 dark:bg-dark-700 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors duration-200">
                  <div className="flex items-center">
                    <FileText className="w-5 h-5 text-gray-600 dark:text-gray-400 mr-3" />
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      Documentation
                    </span>
                  </div>
                  <ExternalLink className="w-4 h-4 text-gray-400" />
                </button>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;