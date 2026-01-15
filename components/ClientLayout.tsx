'use client';

import { AuthProvider, useAuth } from '@/lib/auth';
import Link from 'next/link';
import { LayoutDashboard, Upload, History, FileText, LogOut, User } from 'lucide-react';
import LoginPage from '@/components/LoginPage';

function AppContent({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, user, logout, loading } = useAuth();

    // Show loading state
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    // Show login page if not authenticated
    if (!isAuthenticated) {
        return <LoginPage />;
    }

    // Show main app if authenticated
    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar */}
            <div className="w-64 bg-white border-r flex flex-col">
                <div className="p-6">
                    <h1 className="text-2xl font-bold text-blue-600 flex items-center gap-2">
                        <FileText className="w-8 h-8" />
                        FinDistill
                    </h1>
                </div>
                <nav className="p-4 space-y-2 flex-1">
                    <Link href="/" className="flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors">
                        <LayoutDashboard className="w-5 h-5" />
                        Dashboard
                    </Link>
                    <Link href="/upload" className="flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors">
                        <Upload className="w-5 h-5" />
                        Upload
                    </Link>
                    <Link href="/history" className="flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors">
                        <History className="w-5 h-5" />
                        History
                    </Link>
                </nav>

                {/* User Info & Logout */}
                <div className="p-4 border-t">
                    <div className="flex items-center gap-3 px-4 py-2 text-gray-600 text-sm">
                        <User className="w-4 h-4" />
                        <span className="truncate">{user?.email || 'User'}</span>
                    </div>
                    <button
                        onClick={logout}
                        className="w-full flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors"
                    >
                        <LogOut className="w-5 h-5" />
                        Logout
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto p-8">
                {children}
            </main>
        </div>
    );
}

export default function ClientLayout({ children }: { children: React.ReactNode }) {
    return (
        <AuthProvider>
            <AppContent>{children}</AppContent>
        </AuthProvider>
    );
}
