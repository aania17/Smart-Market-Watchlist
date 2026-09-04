import axios from "axios";

// Set VITE_API_URL in a .env file to point at your deployed backend.
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const client = axios.create({ baseURL: BASE_URL });

// Attach the JWT (if we have one) to every outgoing request.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If the backend says our token is invalid/expired, boot back to login.
client.interceptors.response.use(
  (res) => res,
  (err) => {
    const requestUrl = err.config?.url || "";
    const isAuthenticationRequest = requestUrl.startsWith("/auth/");
    if (err.response?.status === 401 && !isAuthenticationRequest) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default client;
