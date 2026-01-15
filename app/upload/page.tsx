'use client';

import { useState, useCallback } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, FileSpreadsheet, Image } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { apiUrl } from '@/lib/api';

const SUPPORTED_FORMATS = {
    'application/pdf': { label: 'PDF', icon: FileText, color: 'red' },
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': { label: 'Excel', icon: FileSpreadsheet, color: 'green' },
    'application/vnd.ms-excel': { label: 'Excel', icon: FileSpreadsheet, color: 'green' },
    'text/csv': { label: 'CSV', icon: FileSpreadsheet, color: 'blue' },
    'image/png': { label: 'Image', icon: Image, color: 'purple' },
    'image/jpeg': { label: 'Image', icon: Image, color: 'purple' },
    'image/webp': { label: 'Image', icon: Image, color: 'purple' },
};

export default function UploadPage() {
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [errorMessage, setErrorMessage] = useState('');
    const [dragOver, setDragOver] = useState(false);
    const [exportFormat, setExportFormat] = useState<'jsonl' | 'markdown' | 'parquet'>('jsonl');
    const router = useRouter();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setStatus('idle');
            setErrorMessage('');
        }
    };

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setStatus('idle');
            setErrorMessage('');
        }
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
    }, []);

    const handleUpload = async () => {
        if (!file) return;

        setLoading(true);
        setStatus('idle');
        setErrorMessage('');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post(apiUrl(`/api/extract?export_format=${exportFormat}`), formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                timeout: 120000, // 2 minutes for large files
            });

            setStatus('success');

            // Auto-download the converted file in selected format
            const documentId = response.data.document_id;
            if (documentId) {
                const exportUrl = apiUrl(`/api/export/${exportFormat}/${documentId}`);
                window.open(exportUrl, '_blank');
            }

            // Don't auto-redirect to history - stay on the page
        } catch (error: any) {
            console.error(error);
            setStatus('error');

            let msg = 'Failed to process document.';
            if (error.response) {
                // Server responded with a status code
                msg = `Error (${error.response.status}): ${error.response.data?.detail || error.message}`;
            } else if (error.request) {
                // The request was made but no response was received
                msg = 'No response from server. It might be a timeout (processing took too long).';
            } else {
                msg = error.message;
            }
            setErrorMessage(msg);
        } finally {
            setLoading(false);
        }
    };

    const getFileInfo = () => {
        if (!file) return null;
        const format = SUPPORTED_FORMATS[file.type as keyof typeof SUPPORTED_FORMATS];
        return format || { label: 'File', icon: FileText, color: 'gray' };
    };

    const fileInfo = getFileInfo();

    return (
        <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl font-bold mb-2">Upload Document</h2>
            <p className="text-gray-500 mb-8">Upload financial documents for AI-powered distillation</p>

            <div
                className={`bg-white p-12 rounded-xl shadow-sm border-2 border-dashed text-center transition-all
                    ${dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}
                `}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
            >
                <div className="mb-8 flex justify-center">
                    <div className={`w-20 h-20 rounded-full flex items-center justify-center transition-colors
                        ${dragOver ? 'bg-blue-100' : 'bg-blue-50'}
                    `}>
                        <Upload className={`w-10 h-10 transition-colors ${dragOver ? 'text-blue-700' : 'text-blue-600'}`} />
                    </div>
                </div>

                <h3 className="text-xl font-semibold mb-2">Drag and drop your file here</h3>
                <p className="text-gray-500 mb-2">Supported formats:</p>
                <div className="flex flex-wrap justify-center gap-2 mb-8">
                    <span className="px-3 py-1 bg-red-50 text-red-700 rounded-full text-sm font-medium">PDF</span>
                    <span className="px-3 py-1 bg-green-50 text-green-700 rounded-full text-sm font-medium">Excel</span>
                    <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm font-medium">CSV</span>
                    <span className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm font-medium">Images</span>
                </div>

                <input
                    type="file"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                    accept=".pdf,.xlsx,.xls,.csv,image/*"
                />
                <label
                    htmlFor="file-upload"
                    className="inline-block px-6 py-3 bg-white border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors font-medium text-gray-700"
                >
                    Select File
                </label>

                {file && fileInfo && (
                    <div className="mt-6 p-4 bg-gray-50 rounded-lg flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className={`p-2 bg-${fileInfo.color}-100 rounded-lg`}>
                                <fileInfo.icon className={`w-5 h-5 text-${fileInfo.color}-600`} />
                            </div>
                            <div className="text-left">
                                <span className="font-medium text-gray-700 block">{file.name}</span>
                                <span className="text-sm text-gray-500">
                                    {fileInfo.label} • {(file.size / 1024 / 1024).toFixed(2)} MB
                                </span>
                            </div>
                        </div>
                        <span className={`px-2 py-1 bg-${fileInfo.color}-100 text-${fileInfo.color}-700 rounded text-xs font-medium`}>
                            {fileInfo.label}
                        </span>
                    </div>
                )}

                <div className="mt-8">
                    <button
                        onClick={handleUpload}
                        disabled={!file || loading}
                        className={`w-full py-3 rounded-lg font-medium text-white transition-all flex items-center justify-center gap-2
                            ${!file || loading ? 'bg-gray-300 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 shadow-md'}
                        `}
                    >
                        {loading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Processing with AI...
                            </>
                        ) : (
                            'Start Distillation'
                        )}
                    </button>
                </div>

                {status === 'success' && (
                    <div className="mt-4 p-4 bg-green-50 text-green-700 rounded-lg flex items-center gap-2 justify-center">
                        <CheckCircle className="w-5 h-5" />
                        Distillation complete! Your {exportFormat.toUpperCase()} file is downloading...
                    </div>
                )}

                {status === 'error' && (
                    <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-lg flex items-center gap-2 justify-center">
                        <AlertCircle className="w-5 h-5" />
                        {errorMessage}
                    </div>
                )}
            </div>

            {/* Export Format Selector */}
            <div className="mt-8">
                <h3 className="text-lg font-semibold mb-3 text-gray-700">Select Export Format</h3>
                <div className="grid grid-cols-3 gap-4">
                    <button
                        onClick={() => setExportFormat('jsonl')}
                        className={`p-4 rounded-lg text-center transition-all border-2 ${exportFormat === 'jsonl'
                            ? 'bg-purple-100 border-purple-500 shadow-md'
                            : 'bg-purple-50 border-transparent hover:border-purple-300'
                            }`}
                    >
                        <h4 className={`font-semibold ${exportFormat === 'jsonl' ? 'text-purple-800' : 'text-purple-700'}`}>
                            JSONL
                        </h4>
                        <p className="text-sm text-purple-600">LLM Fine-tuning</p>
                        {exportFormat === 'jsonl' && (
                            <span className="inline-block mt-2 px-2 py-0.5 bg-purple-500 text-white text-xs rounded-full">Selected</span>
                        )}
                    </button>
                    <button
                        onClick={() => setExportFormat('markdown')}
                        className={`p-4 rounded-lg text-center transition-all border-2 ${exportFormat === 'markdown'
                            ? 'bg-green-100 border-green-500 shadow-md'
                            : 'bg-green-50 border-transparent hover:border-green-300'
                            }`}
                    >
                        <h4 className={`font-semibold ${exportFormat === 'markdown' ? 'text-green-800' : 'text-green-700'}`}>
                            Markdown
                        </h4>
                        <p className="text-sm text-green-600">RAG Systems</p>
                        {exportFormat === 'markdown' && (
                            <span className="inline-block mt-2 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full">Selected</span>
                        )}
                    </button>
                    <button
                        onClick={() => setExportFormat('parquet')}
                        className={`p-4 rounded-lg text-center transition-all border-2 ${exportFormat === 'parquet'
                            ? 'bg-orange-100 border-orange-500 shadow-md'
                            : 'bg-orange-50 border-transparent hover:border-orange-300'
                            }`}
                    >
                        <h4 className={`font-semibold ${exportFormat === 'parquet' ? 'text-orange-800' : 'text-orange-700'}`}>
                            Parquet
                        </h4>
                        <p className="text-sm text-orange-600">Analytics</p>
                        {exportFormat === 'parquet' && (
                            <span className="inline-block mt-2 px-2 py-0.5 bg-orange-500 text-white text-xs rounded-full">Selected</span>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
