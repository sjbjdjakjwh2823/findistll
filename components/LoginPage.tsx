'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { FileText, Mail, Lock, User, Loader2, ArrowRight, Sparkles } from 'lucide-react';

// Google and GitHub icons as SVG
const GoogleIcon = () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
);

const GitHubIcon = () => (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
    </svg>
);

export default function LoginPage() {
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [loading, setLoading] = useState(false);
    const [oauthLoading, setOauthLoading] = useState<'google' | 'github' | null>(null);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const { login, register, signInWithOAuth } = useAuth();

    // Load saved email on mount
    useEffect(() => {
        const savedEmail = localStorage.getItem('remembered_email');
        if (savedEmail) {
            setEmail(savedEmail);
            setRememberMe(true);
        }
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        setSuccessMessage('');

        try {
            if (isLogin) {
                await login(email, password);

                // Save email if Remember Me is checked (after successful login)
                if (rememberMe) {
                    localStorage.setItem('remembered_email', email);
                } else {
                    localStorage.removeItem('remembered_email');
                }
            } else {
                // Registration - don't auto-login, show success message
                const result = await register(email, password, fullName);

                if (result.success) {
                    // Clear form
                    setEmail('');
                    setPassword('');
                    setFullName('');

                    // Switch to login mode
                    setIsLogin(true);

                    // Show success message
                    if (result.requiresEmailConfirmation) {
                        setSuccessMessage('Registration complete! Please check your email for confirmation before logging in. 📧');
                    } else {
                        setSuccessMessage('Registration complete. Please log in to continue. ✅');
                    }
                }
            }
        } catch (err: any) {
            console.error('Auth error:', err);

            // Clear saved credentials on login failure
            if (isLogin) {
                localStorage.removeItem('remembered_email');
                setRememberMe(false);
            }

            const detail = err.response?.data?.detail
                || err.response?.data?.msg
                || err.response?.data?.error_description
                || err.message;

            setError(detail ? `Error: ${detail}` : 'Authentication failed. Please check your connection.');
        } finally {
            setLoading(false);
        }
    };

    const handleOAuthLogin = async (provider: 'google' | 'github') => {
        setOauthLoading(provider);
        setError('');
        try {
            await signInWithOAuth(provider);
        } catch (err: any) {
            console.error('OAuth error:', err);
            // Show detailed error message
            setError(err.message || `Failed to sign in with ${provider}`);
            setOauthLoading(null);
        }
    };

    return (
        <div className="min-h-screen flex">
            {/* Left Side - Branding */}
            <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-blue-600 via-purple-600 to-indigo-700 p-12 flex-col justify-between">
                <div>
                    <div className="flex items-center gap-3 text-white">
                        <FileText className="w-10 h-10" />
                        <span className="text-3xl font-bold">FinDistill</span>
                    </div>
                </div>

                <div className="space-y-6">
                    <h1 className="text-4xl lg:text-5xl font-bold text-white leading-tight">
                        Transform your<br />
                        <span className="text-yellow-300">financial documents</span><br />
                        into AI-ready data
                    </h1>
                    <p className="text-blue-100 text-lg max-w-md">
                        Upload PDFs, Excel files, or images and instantly convert them to JSONL or Markdown format for LLM fine-tuning and RAG systems.
                    </p>
                    <div className="flex items-center gap-4 text-white/80">
                        <div className="flex items-center gap-2">
                            <Sparkles className="w-5 h-5 text-yellow-300" />
                            <span>AI-Powered</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Sparkles className="w-5 h-5 text-yellow-300" />
                            <span>Multi-format</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Sparkles className="w-5 h-5 text-yellow-300" />
                            <span>Instant Export</span>
                        </div>
                    </div>
                </div>

                <div className="text-blue-200 text-sm">
                    © 2026 FinDistill. All rights reserved.
                </div>
            </div>

            {/* Right Side - Auth Form */}
            <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-gray-50">
                <div className="w-full max-w-md">
                    {/* Mobile Logo */}
                    <div className="lg:hidden mb-8 text-center">
                        <div className="flex items-center justify-center gap-2 text-blue-600">
                            <FileText className="w-8 h-8" />
                            <span className="text-2xl font-bold">FinDistill</span>
                        </div>
                    </div>

                    <div className="bg-white rounded-2xl shadow-xl p-8">
                        <div className="text-center mb-8">
                            <h2 className="text-2xl font-bold text-gray-900">
                                {isLogin ? 'Welcome back' : 'Create your account'}
                            </h2>
                            <p className="text-gray-500 mt-2">
                                {isLogin ? 'Sign in to continue to FinDistill' : 'Start transforming documents today'}
                            </p>
                        </div>

                        {/* OAuth Buttons */}
                        <div className="space-y-3 mb-6">
                            <button
                                onClick={() => handleOAuthLogin('google')}
                                disabled={oauthLoading !== null}
                                className="w-full py-3 px-4 bg-white border border-gray-300 text-gray-700 font-medium rounded-xl hover:bg-gray-50 focus:ring-4 focus:ring-gray-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
                            >
                                {oauthLoading === 'google' ? (
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                ) : (
                                    <GoogleIcon />
                                )}
                                Continue with Google
                            </button>

                            <button
                                onClick={() => handleOAuthLogin('github')}
                                disabled={oauthLoading !== null}
                                className="w-full py-3 px-4 bg-gray-900 text-white font-medium rounded-xl hover:bg-gray-800 focus:ring-4 focus:ring-gray-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
                            >
                                {oauthLoading === 'github' ? (
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                ) : (
                                    <GitHubIcon />
                                )}
                                Continue with GitHub
                            </button>
                        </div>

                        {/* Divider */}
                        <div className="relative my-6">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-gray-200"></div>
                            </div>
                            <div className="relative flex justify-center text-sm">
                                <span className="px-4 bg-white text-gray-500">or continue with email</span>
                            </div>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-5">
                            {!isLogin && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Full Name
                                    </label>
                                    <div className="relative">
                                        <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                                        <input
                                            type="text"
                                            value={fullName}
                                            onChange={(e) => setFullName(e.target.value)}
                                            className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                            placeholder="John Doe"
                                        />
                                    </div>
                                </div>
                            )}

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Email Address
                                </label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                        placeholder="you@example.com"
                                        required
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Password
                                </label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <input
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                        placeholder="••••••••"
                                        required
                                        minLength={6}
                                    />
                                </div>
                            </div>

                            {/* Remember Me - only shown in login mode */}
                            {isLogin && (
                                <div className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        id="rememberMe"
                                        checked={rememberMe}
                                        onChange={(e) => setRememberMe(e.target.checked)}
                                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                    />
                                    <label
                                        htmlFor="rememberMe"
                                        className="text-sm text-gray-600 cursor-pointer select-none"
                                    >
                                        Keep me signed in (Remember email)
                                    </label>
                                </div>
                            )}

                            {successMessage && (
                                <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
                                    {successMessage}
                                </div>
                            )}

                            {error && (
                                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
                                    {error}
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-medium rounded-xl hover:from-blue-700 hover:to-purple-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        {isLogin ? 'Signing in...' : 'Creating account...'}
                                    </>
                                ) : (
                                    <>
                                        {isLogin ? 'Sign In' : 'Create Account'}
                                        <ArrowRight className="w-5 h-5" />
                                    </>
                                )}
                            </button>
                        </form>

                        <div className="mt-6 text-center">
                            <button
                                onClick={() => {
                                    setIsLogin(!isLogin);
                                    setError('');
                                    setSuccessMessage('');
                                }}
                                className="text-blue-600 hover:text-blue-700 font-medium transition-colors"
                            >
                                {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
                            </button>
                        </div>
                    </div>

                    <p className="mt-6 text-center text-gray-400 text-sm">
                        By continuing, you agree to our Terms of Service and Privacy Policy.
                    </p>
                </div>
            </div>
        </div>
    );
}
