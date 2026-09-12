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

  constructor() {
    this.instance = axios.create({
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
      // Route through BFF proxy: /api/proxy?path=/api/v1{url}
      const fullUrl = `/api/proxy?path=/api/v1${url}`;
      const response = await this.instance.get<T>(fullUrl, { params });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async post<T>(url: string, data?: Record<string, any>): Promise<T> {
    try {
      const fullUrl = `/api/proxy?path=/api/v1${url}`;
      const response = await this.instance.post<T>(fullUrl, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async patch<T>(url: string, data?: Record<string, any>): Promise<T> {
    try {
      const fullUrl = `/api/proxy?path=/api/v1${url}`;
      const response = await this.instance.patch<T>(fullUrl, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async put<T>(url: string, data?: Record<string, any>): Promise<T> {
    try {
      const fullUrl = `/api/proxy?path=/api/v1${url}`;
      const response = await this.instance.put<T>(fullUrl, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async delete<T>(url: string): Promise<T> {
    try {
      const fullUrl = `/api/proxy?path=/api/v1${url}`;
      const response = await this.instance.delete<T>(fullUrl);
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
