'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { FileText, Calendar, ChevronRight } from 'lucide-react';
import { apiUrl } from '@/lib/api';

interface HistoryItem {
    id: number;
    filename: string;
    upload_date: string;
    title: string;
    summary: string;
}

export default function HistoryPage() {
    const [history, setHistory] = useState<HistoryItem[]>([]);

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await axios.get(apiUrl('/api/history'));
                setHistory(res.data);
            } catch (error) {
                console.error('Failed to fetch history', error);
            }
        };
        fetchHistory();
    }, []);

    return (
        <div>
            <h2 className="text-3xl font-bold mb-8">Extraction History</h2>

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
                                    <p className="text-sm text-gray-500 mb-2 flex items-center gap-1">
                                        <Calendar className="w-4 h-4" />
                                        {new Date(item.upload_date).toLocaleDateString()}
                                    </p>
                                    <p className="text-gray-600 line-clamp-2">{item.summary}</p>
                                </div>
                            </div>

                            <button className="p-2 hover:bg-gray-50 rounded-full transition-colors">
                                <ChevronRight className="w-5 h-5 text-gray-400" />
                            </button>
                        </div>
                        <div className="mt-4 pt-4 border-t flex justify-between items-center text-sm text-gray-500">
                            <span>{item.filename}</span>
                            <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">Completed</span>
                        </div>
                    </div>
                ))}

                {history.length === 0 && (
                    <div className="text-center py-12 text-gray-500 bg-white rounded-xl border border-dashed">
                        No history found. Upload a document to get started.
                    </div>
                )}
            </div>
        </div>
    );
}
