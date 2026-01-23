import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import Dashboard from './pages/Dashboard';
import Mergers from './pages/Mergers';
import MergerDetail from './pages/MergerDetail';
import Timeline from './pages/Timeline';
import Industries from './pages/Industries';

function App() {
  return (
    <HelmetProvider>
      <Router>
        <ErrorBoundary>
          <div className="min-h-screen bg-gray-50 flex flex-col">
            <Navbar />
            <main id="main-content" className="flex-grow pt-16">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/mergers" element={<Mergers />} />
                <Route path="/mergers/:id" element={<MergerDetail />} />
                <Route path="/timeline" element={<Timeline />} />
                <Route path="/industries" element={<Industries />} />
              </Routes>
            </main>
            <Footer />
          </div>
        </ErrorBoundary>
      </Router>
    </HelmetProvider>
  );
}

export default App;
