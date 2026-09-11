/**
 * Typed API client for Django DRF backend.
 *
 * All requests flow through Next.js route handlers (BFF):
 * Browser → Next.js → Django
 *
 * Never calls Django directly from the browser.
 * Route handlers refresh tokens and handle auth transparently.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

interface ApiError {
  status: number;
  data: Record<string, any>;
  message: string;
}

interface ApiResponse<T> {
  data: T;
  status: number;
}

class ApiClient {
  private instance: AxiosInstance;
  private baseURL: string;

  constructor(baseURL: string = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1') {
    this.baseURL = baseURL;
    this.instance = axios.create({
      baseURL,
      withCredentials: true, // Send httpOnly cookies
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.instance.interceptors.request.use((config) => {
      config.headers['Content-Type'] = 'application/json';
      return config;
    });

    // Response interceptor for error handling
    this.instance.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Session expired or invalid — let route handlers handle refresh
          window.location.href = '/auth/login';
        }
        throw error;
      }
    );
  }

  async get<T>(url: string, params?: Record<string, any>): Promise<T> {
    try {
      const response = await this.instance.get<T>(url, { params });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async post<T>(url: string, data?: Record<string, any>): Promise<T> {
    try {
      const response = await this.instance.post<T>(url, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async patch<T>(url: string, data?: Record<string, any>): Promise<T> {
    try {
      const response = await this.instance.patch<T>(url, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async put<T>(url: string, data?: Record<string, any>): Promise<T> {
    try {
      const response = await this.instance.put<T>(url, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async delete<T>(url: string): Promise<T> {
    try {
      const response = await this.instance.delete<T>(url);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  private handleError(error: any): ApiError {
    if (error.response) {
      return {
        status: error.response.status,
        data: error.response.data,
        message: error.response.data?.detail || error.message,
      };
    }
    return {
      status: 0,
      data: {},
      message: error.message || 'Unknown error',
    };
  }
}

export const apiClient = new ApiClient();
export type { ApiError, ApiResponse };
