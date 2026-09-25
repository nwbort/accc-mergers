import { Component } from 'react';
import { FaExclamationTriangle } from 'react-icons/fa';
import ErrorCard from './ErrorCard';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log error details for debugging
    if (import.meta.env.DEV) {
      console.error('Error caught by boundary:', error, errorInfo);
    }
  }

  render() {
    if (this.state.hasError) {
      // AppContent (navbar and all) is gone, so this stands alone on the
      // page background rather than inside <main>.
      return (
        <div className="min-h-screen gradient-mesh flex items-center">
          <div className="w-full">
            <ErrorCard
              icon={FaExclamationTriangle}
              title="Something went wrong"
              message="An unexpected error occurred. Please try refreshing the page."
              primaryAction={{ label: 'Refresh page', onClick: () => window.location.reload() }}
            />
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
