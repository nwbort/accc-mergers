// API configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  mergers: `${API_BASE_URL}/api/mergers`,
  merger: (id) => `${API_BASE_URL}/api/mergers/${id}`,
  stats: `${API_BASE_URL}/api/stats`,
  timeline: `${API_BASE_URL}/api/timeline`,
  industries: `${API_BASE_URL}/api/industries`,
  upcomingEvents: `${API_BASE_URL}/api/upcoming-events`,
};
