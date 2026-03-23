import { StrictMode } from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const root = document.getElementById('root');
const app = (
  <StrictMode>
    <App />
  </StrictMode>
);

if (root.dataset.prerendered) {
  hydrateRoot(root, app, {
    onRecoverableError() {}, // suppress hydration mismatch warnings (expected due to dynamic data)
  });
} else {
  createRoot(root).render(app);
}
