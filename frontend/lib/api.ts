/**
 * API Configuration for FinDistill
 * 
 * Automatically detects development vs production environment
 * and sets the appropriate API base URL.
 */

/**
 * Get the API base URL based on the current environment.
 * - Development (localhost): Uses local FastAPI server directly (or via proxy if we changed this to '')
 * - Production (Vercel): Uses relative paths (same domain)
 */
export const getApiBaseUrl = (): string => {
    // Server-side rendering check
    if (typeof window === 'undefined') {
        // On server, use relative URL (Vercel handles routing)
        return '';
    }

    // Client-side: detect environment
    const hostname = window.location.hostname;

    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        // Local development - use local FastAPI server
        return 'http://localhost:8000';
    }

    // Production - use relative URL (same Vercel domain)
    return '';
};

/**
 * Pre-computed API base URL for convenience.
 * Use getApiBaseUrl() if you need dynamic evaluation.
 */
export const API_BASE_URL = getApiBaseUrl();

/**
 * Build a full API endpoint URL.
 * @param path - API path starting with /api/
 * @returns Full URL for the API endpoint
 */
export const apiUrl = (path: string): string => {
    const base = getApiBaseUrl();
    // Ensure path starts with /
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${base}${normalizedPath}`;
};
