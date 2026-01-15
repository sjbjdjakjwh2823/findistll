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

// Supabase URL for OAuth (hardcoded to match backend)
const SUPABASE_URL = 'https://nnuixqxmalttautcqckt.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5udWl4cXhtYWx0dGF1dGNxY2t0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgzNjQ1NjIsImV4cCI6MjA4Mzk0MDU2Mn0.RKQm2hVC7IkuW_ldtGedJQtWr15RrAJYWWMkJ5SWdAM';

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
            // Check hash fragment for OAuth tokens
            const hashParams = new URLSearchParams(window.location.hash.substring(1));
            const accessToken = hashParams.get('access_token');
            const refreshToken = hashParams.get('refresh_token');

            if (accessToken) {
                localStorage.setItem('access_token', accessToken);
                if (refreshToken) {
                    localStorage.setItem('refresh_token', refreshToken);
                }
                setToken(accessToken);
                fetchUser(accessToken);

                // Clear the hash from URL
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

        // Build Supabase OAuth URL
        const authUrl = new URL(`${SUPABASE_URL}/auth/v1/authorize`);
        authUrl.searchParams.set('provider', provider);
        authUrl.searchParams.set('redirect_to', redirectTo);

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
