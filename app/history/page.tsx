'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { FileText, Calendar, ChevronRight, Download, FileJson, FileType, Database, HardDrive } from 'lucide-react';
import { apiUrl } from '@/lib/api';

interface ExportLinks {
    jsonl: string;
    markdown: string;
    parquet: string;
    hdf5: string;
}

interface HistoryItem {
    id: number;
    filename: string;
    file_type: string;
    upload_date: string;
    title: string;
    summary: string;
    exports: ExportLinks;
}

export default function HistoryPage() {
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                // Get auth token from localStorage
                const token = localStorage.getItem('access_token');

                const res = await axios.get(apiUrl('/api/history'), {
                    headers: token ? { Authorization: `Bearer ${token}` } : {}
                });
                setHistory(res.data);
            } catch (error: any) {
                console.error('Failed to fetch history', error);
                if (error.response?.status === 401) {
                    setError('Authentication required. Please log in.');
                } else {
                    setError('Failed to load history. Please try again later.');
                }
            } finally {
                setLoading(false);
            }
        };
        fetchHistory();
    }, []);

    const handleExport = (url: string, format: string) => {
        window.open(apiUrl(url), '_blank');
    };

    const getFileTypeLabel = (mimeType: string) => {
        if (!mimeType) return 'Unknown';
        if (mimeType.includes('pdf')) return 'PDF';
        if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return 'Excel';
        if (mimeType.includes('csv')) return 'CSV';
        if (mimeType.includes('image')) return 'Image';
        return 'File';
    };

    return (
        <div>
            <h2 className="text-3xl font-bold mb-2">Extraction History</h2>
            <p className="text-gray-500 mb-8">View and export your processed documents</p>

            {loading ? (
                <div className="flex justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
            ) : error ? (
                <div className="text-center py-12 text-red-500 bg-red-50 rounded-xl border border-red-200">
                    <p>{error}</p>
                </div>
            ) : (
                <div className="grid gap-4">
                    {history.map((item) => (
                        <div key={item.id} className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex justify-between items-start">
                                <div className="flex items-start gap-4">
                                    <div className="p-3 bg-blue-50 rounded-lg">
                                        <FileText className="w-6 h-6 text-blue-600" />
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-semibold text-gray-900">{item.title}</h3>
                                        <p className="text-sm text-gray-500 mb-2 flex items-center gap-2">
                                            <Calendar className="w-4 h-4" />
                                            {new Date(item.upload_date).toLocaleDateString()}
                                            <span className="px-2 py-0.5 bg-gray-100 rounded text-xs">
                                                {getFileTypeLabel(item.file_type)}
                                            </span>
                                        </p>
                                        <p className="text-gray-600 line-clamp-2">{item.summary}</p>
                                    </div>
                                </div>

                                <button className="p-2 hover:bg-gray-50 rounded-full transition-colors">
                                    <ChevronRight className="w-5 h-5 text-gray-400" />
                                </button>
                            </div>

                            {/* Export Buttons */}
                            <div className="mt-4 pt-4 border-t flex flex-wrap justify-between items-center gap-2">
                                <span className="text-sm text-gray-500">{item.filename}</span>

                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={() => handleExport(item.exports.jsonl, 'jsonl')}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-lg text-sm font-medium transition-colors"
                                        title="JSONL for LLM Fine-tuning"
                                    >
                                        <FileJson className="w-4 h-4" />
                                        JSONL
                                    </button>
                                    <button
                                        onClick={() => handleExport(item.exports.markdown, 'markdown')}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-green-50 hover:bg-green-100 text-green-700 rounded-lg text-sm font-medium transition-colors"
                                        title="Markdown for RAG"
                                    >
                                        <FileType className="w-4 h-4" />
                                        Markdown
                                    </button>
                                    <button
                                        onClick={() => handleExport(item.exports.parquet, 'parquet')}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-orange-50 hover:bg-orange-100 text-orange-700 rounded-lg text-sm font-medium transition-colors"
                                        title="Parquet for Analytics"
                                    >
                                        <Database className="w-4 h-4" />
                                        Parquet
                                    </button>
                                    <button
                                        onClick={() => handleExport(item.exports.hdf5, 'hdf5')}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-sm font-medium transition-colors"
                                        title="HDF5 for AI/ML Training"
                                    >
                                        <HardDrive className="w-4 h-4" />
                                        HDF5
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}

                    {history.length === 0 && (
                        <div className="text-center py-12 text-gray-500 bg-white rounded-xl border border-dashed">
                            <p className="mb-2">No history found.</p>
                            <p>Upload a document to get started.</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

