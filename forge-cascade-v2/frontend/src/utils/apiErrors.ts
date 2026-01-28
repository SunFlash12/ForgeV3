import axios from 'axios';

export type ApiErrorCategory = 'NETWORK' | 'AUTH' | 'SERVER' | 'NOT_FOUND' | 'UNKNOWN';

export interface ClassifiedError {
  category: ApiErrorCategory;
  message: string;
  technical: string;
  retryable: boolean;
  statusCode?: number;
}

export function classifyError(error: unknown): ClassifiedError {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
        return {
          category: 'NETWORK',
          message: 'Request timed out. The server may be overloaded.',
          technical: `Timeout: ${error.message}`,
          retryable: true,
        };
      }
      return {
        category: 'NETWORK',
        message: 'Cannot connect to the Forge backend. The server may be offline.',
        technical: error.message || 'Network error',
        retryable: true,
      };
    }

    const status = error.response.status;
    const detail =
      typeof error.response.data === 'object' &&
      error.response.data !== null &&
      'detail' in error.response.data
        ? String((error.response.data as { detail: unknown }).detail)
        : '';

    if (status === 401) {
      return {
        category: 'AUTH',
        message: 'You need to sign in to access this content.',
        technical: detail || 'Unauthorized',
        retryable: false,
        statusCode: 401,
      };
    }

    if (status === 403) {
      return {
        category: 'AUTH',
        message: 'You do not have permission to access this resource.',
        technical: detail || 'Forbidden',
        retryable: false,
        statusCode: 403,
      };
    }

    if (status === 404) {
      return {
        category: 'NOT_FOUND',
        message: 'The requested resource was not found.',
        technical: detail || 'Not found',
        retryable: false,
        statusCode: 404,
      };
    }

    if (status >= 500) {
      return {
        category: 'SERVER',
        message: 'The server encountered an error. Please try again shortly.',
        technical: detail || `Server error ${status}`,
        retryable: true,
        statusCode: status,
      };
    }

    return {
      category: 'UNKNOWN',
      message: 'An unexpected error occurred.',
      technical: detail || `HTTP ${status}`,
      retryable: true,
      statusCode: status,
    };
  }

  if (error instanceof Error) {
    return {
      category: 'UNKNOWN',
      message: 'An unexpected error occurred.',
      technical: error.message,
      retryable: true,
    };
  }

  return {
    category: 'UNKNOWN',
    message: 'An unexpected error occurred.',
    technical: String(error),
    retryable: true,
  };
}

export function isNetworkError(error: unknown): boolean {
  return classifyError(error).category === 'NETWORK';
}

export function isAuthError(error: unknown): boolean {
  return classifyError(error).category === 'AUTH';
}
