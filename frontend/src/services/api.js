/**
 * Backend API client.
 *
 * All data fetching lives here — never inline in components. That keeps mocking
 * trivial while the backend is still returning 501s.
 */
import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('vayux_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('vayux_token');
    }
    return Promise.reject(error);
  },
);

export const cyclones = {
  listActive: () => client.get('/cyclones/active').then((r) => r.data),
  list: (params) => client.get('/cyclones', { params }).then((r) => r.data),
  get: (id) => client.get(`/cyclones/${id}`).then((r) => r.data),
  track: (id) => client.get(`/cyclones/${id}/track`).then((r) => r.data),
  observations: (id, params) =>
    client.get(`/cyclones/${id}/observations`, { params }).then((r) => r.data),
};

export const predictions = {
  latest: (cycloneId) => client.get(`/predictions/${cycloneId}`).then((r) => r.data),
  history: (cycloneId) => client.get(`/predictions/${cycloneId}/history`).then((r) => r.data),
  run: (payload) => client.post('/predictions/run', payload).then((r) => r.data),
};

export const alerts = {
  list: (params) => client.get('/alerts', { params }).then((r) => r.data),
  get: (id) => client.get(`/alerts/${id}`).then((r) => r.data),
  acknowledge: (id) => client.post(`/alerts/${id}/acknowledge`).then((r) => r.data),
  cancel: (id) => client.post(`/alerts/${id}/cancel`).then((r) => r.data),
};

export const imagery = {
  frames: (params) => client.get('/imagery/frames', { params }).then((r) => r.data),
  overlay: (cycloneId) => client.get(`/imagery/overlay/${cycloneId}`).then((r) => r.data),
  explain: (observationId) =>
    client.get(`/imagery/explain/${observationId}`).then((r) => r.data),
};

export const system = {
  version: () => client.get('/version').then((r) => r.data),
  health: () => client.get('/health').then((r) => r.data),
  pipeline: () => client.get('/pipeline/status').then((r) => r.data),
};

export const auth = {
  login: (username, password) =>
    client.post('/auth/login', { username, password }).then((r) => r.data),
  me: () => client.get('/auth/me').then((r) => r.data),
};

export default client;
