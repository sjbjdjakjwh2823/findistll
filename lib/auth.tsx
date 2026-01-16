'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';
import { apiUrl } from './api';

interface User {
    id: string;
    email: string;
    role?: string;
    metadata?: any;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, fullName?: string) => Promise<void>;
    signInWithOAuth: (provider: 'google' | 'github') => Promise<void>;
    logout: () => void;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Supabase URL for OAuth - loaded from environment variables
// NEXT_PUBLIC_ prefix required for client-side access in Next.js
const SUPABASE_URL = process.env.NEXT_PUBLIC_SB_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SB_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';


export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    // Check for existing token on mount
    useEffect(() => {
        const storedToken = localStorage.getItem('access_token');
        if (storedToken) {
            setToken(storedToken);
            fetchUser(storedToken);
        } else {
            setLoading(false);
        }
    }, []);

    // Handle OAuth callback - check URL for tokens
    useEffect(() => {
        const handleOAuthCallback = () => {
            // Check hash fragment for OAuth tokens (Supabase implicit flow)
            let accessToken: string | null = null;
            let refreshToken: string | null = null;

            // Try hash fragment first (#access_token=...)
            if (window.location.hash) {
                const hashParams = new URLSearchParams(window.location.hash.substring(1));
                accessToken = hashParams.get('access_token');
                refreshToken = hashParams.get('refresh_token');
                console.log('[OAuth] Found hash params, access_token:', accessToken ? 'present' : 'null');
            }

            // Also check query params (?access_token=...)
            if (!accessToken && window.location.search) {
                const queryParams = new URLSearchParams(window.location.search);
                accessToken = queryParams.get('access_token');
                refreshToken = queryParams.get('refresh_token');
                console.log('[OAuth] Found query params, access_token:', accessToken ? 'present' : 'null');
            }

            if (accessToken) {
                console.log('[OAuth] Storing token and fetching user...');
                localStorage.setItem('access_token', accessToken);
                if (refreshToken) {
                    localStorage.setItem('refresh_token', refreshToken);
                }
                setToken(accessToken);
                fetchUser(accessToken);

                // Clear the hash/query from URL
                window.history.replaceState(null, '', window.location.pathname);
            }
        };

        handleOAuthCallback();
    }, []);

    const fetchUser = async (accessToken: string) => {
        try {
            const response = await axios.get(apiUrl('/api/auth/me'), {
                headers: { Authorization: `Bearer ${accessToken}` }
            });
            setUser(response.data);
        } catch (error) {
            console.error('Failed to fetch user:', error);
            localStorage.removeItem('access_token');
            setToken(null);
        } finally {
            setLoading(false);
        }
    };

    const login = async (email: string, password: string) => {
        const response = await axios.post(apiUrl('/api/auth/login'), {
            email,
            password
        });

        const { access_token, user: userData } = response.data;
        localStorage.setItem('access_token', access_token);
        setToken(access_token);

        if (userData) {
            setUser({
                id: userData.id,
                email: userData.email,
                role: userData.role
            });
        } else {
            await fetchUser(access_token);
        }
    };

    const register = async (email: string, password: string, fullName?: string) => {
        const response = await axios.post(apiUrl('/api/auth/register'), {
            email,
            password,
            full_name: fullName
        });

        const { access_token, user: userData } = response.data;
        if (access_token) {
            localStorage.setItem('access_token', access_token);
            setToken(access_token);

            if (userData) {
                setUser({
                    id: userData.id,
                    email: userData.email,
                    role: userData.role
                });
            }
        }
    };

    const signInWithOAuth = async (provider: 'google' | 'github') => {
        // Get the current origin for redirect
        const redirectTo = typeof window !== 'undefined'
            ? `${window.location.origin}/`
            : '';

        console.log('[OAuth] Starting OAuth flow for:', provider);
        console.log('[OAuth] SUPABASE_URL:', SUPABASE_URL);
        console.log('[OAuth] Has ANON_KEY:', !!SUPABASE_ANON_KEY);
        console.log('[OAuth] Redirect to:', redirectTo);

        // Build Supabase OAuth URL
        const authUrl = new URL(`${SUPABASE_URL}/auth/v1/authorize`);
        authUrl.searchParams.set('provider', provider);
        authUrl.searchParams.set('redirect_to', redirectTo);

        // IMPORTANT: Add apikey - required for Supabase OAuth
        if (SUPABASE_ANON_KEY) {
            authUrl.searchParams.set('apikey', SUPABASE_ANON_KEY);
        }

        console.log('[OAuth] Full OAuth URL:', authUrl.toString());

        // Redirect to OAuth provider
        window.location.href = authUrl.toString();
    };

    const logout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{
            user,
            token,
            loading,
            login,
            register,
            signInWithOAuth,
            logout,
            isAuthenticated: !!token
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
