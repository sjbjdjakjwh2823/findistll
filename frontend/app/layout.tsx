import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Link from 'next/link'
import { LayoutDashboard, Upload, History, FileText } from 'lucide-react'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
    title: 'FinDistill',
    description: 'Financial Document Distillery',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body className={inter.className}>
                <div className="flex h-screen bg-gray-50">
                    {/* Sidebar */}
                    <div className="w-64 bg-white border-r">
                        <div className="p-6">
                            <h1 className="text-2xl font-bold text-blue-600 flex items-center gap-2">
                                <FileText className="w-8 h-8" />
                                FinDistill
                            </h1>
                        </div>
                        <nav className="p-4 space-y-2">
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
                    </div>

                    {/* Main Content */}
                    <main className="flex-1 overflow-y-auto p-8">
                        {children}
                    </main>
                </div>
            </body>
        </html>
    )
}
