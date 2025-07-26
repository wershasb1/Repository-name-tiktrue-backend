import React from 'react';
import { motion } from 'framer-motion';
import { 
  Shield, 
  Zap, 
  Globe, 
  Users, 
  Settings,
  Download,
  Lock,
  Cpu,
  HardDrive,
  Wifi,
  CheckCircle,
  ArrowRight
} from 'lucide-react';
import { Link } from 'react-router-dom';

const FeaturesPage = () => {
  const mainFeatures = [
    {
      icon: <Shield className="w-12 h-12" />,
      title: "Enhanced Security & Privacy",
      description: "Your sensitive data never leaves your local network. Complete offline processing ensures maximum security.",
      benefits: [
        "Zero data transmission to external servers",
        "Local network processing only",
        "End-to-end encryption",
        "GDPR and compliance ready"
      ]
    },
    {
      icon: <Zap className="w-12 h-12" />,
      title: "Cost-Effective Solution",
      description: "Dramatically reduce infrastructure costs compared to cloud-based AI solutions.",
      benefits: [
        "No expensive cloud subscriptions",
        "Use existing hardware resources",
        "Scale without additional costs",
        "ROI within first month"
      ]
    },
    {
      icon: <Globe className="w-12 h-12" />,
      title: "Complete Offline Functionality",
      description: "Enjoy continuous AI operations even without an internet connection.",
      benefits: [
        "No internet dependency",
        "24/7 availability",
        "Remote location support",
        "Disaster-proof operations"
      ]
    },
    {
      icon: <Users className="w-12 h-12" />,
      title: "Simple Scalability",
      description: "Effortlessly increase your AI processing power by adding any device to the network.",
      benefits: [
        "Add devices instantly",
        "Automatic load balancing",
        "Dynamic resource allocation",
        "Horizontal scaling"
      ]
    }
  ];

  return (
    <div className="min-h-screen pt-20">
      {/* Hero Section */}
      <section className="hero-gradient py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <h1 className="text-5xl md:text-6xl font-bold text-gray-900 dark:text-white mb-6">
              Powerful Features for
              <span className="gradient-text block">Distributed AI</span>
            </h1>
            <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto mb-8">
              Discover how TikTrue's MDI-LLM platform revolutionizes AI processing 
              with cutting-edge distributed computing technology.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Main Features */}
      <section className="py-20 bg-white dark:bg-dark-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-6">
              Core Features
            </h2>
            <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
              Everything you need for enterprise-grade distributed AI processing
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-12">
            {mainFeatures.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="card p-8"
              >
                <div className="text-primary-600 dark:text-primary-400 mb-6">
                  {feature.icon}
                </div>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  {feature.title}
                </h3>
                <p className="text-gray-600 dark:text-gray-300 mb-6">
                  {feature.description}
                </p>
                <ul className="space-y-2">
                  {feature.benefits.map((benefit, idx) => (
                    <li key={idx} className="flex items-center text-gray-700 dark:text-gray-300">
                      <CheckCircle className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" />
                      {benefit}
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-primary-600 dark:bg-primary-700">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
              Ready to Experience These Features?
            </h2>
            <p className="text-xl text-primary-100 mb-8">
              Start your free trial today and see how TikTrue can transform your AI operations.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                to="/register"
                className="bg-white text-primary-600 hover:bg-gray-100 font-semibold py-4 px-8 rounded-lg text-lg transition-colors duration-200 inline-flex items-center justify-center gap-2"
              >
                Start Free Trial
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link
                to="/pricing"
                className="border-2 border-white text-white hover:bg-white hover:text-primary-600 font-semibold py-4 px-8 rounded-lg text-lg transition-colors duration-200 inline-flex items-center justify-center gap-2"
              >
                View Pricing
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default FeaturesPage;