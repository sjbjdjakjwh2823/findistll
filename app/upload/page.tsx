'use client';

import { useState, useCallback, useRef } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, FileSpreadsheet, Image, Download, X } from 'lucide-react';
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

interface FileResult {
    file: File;
    status: 'pending' | 'processing' | 'success' | 'error';
    downloadUrl?: string;
    error?: string;
}

const MAX_FILES = 5;

type ExportFormat = 'jsonl' | 'markdown';

export default function UploadPage() {
    const [files, setFiles] = useState<FileResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [exportFormat, setExportFormat] = useState<ExportFormat>('jsonl');
    const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const router = useRouter();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            addFiles(Array.from(e.target.files));
        }
    };

    const addFiles = (newFiles: File[]) => {
        const remainingSlots = MAX_FILES - files.length;
        const filesToAdd = newFiles.slice(0, remainingSlots).map(file => ({
            file,
            status: 'pending' as const
        }));

        if (filesToAdd.length > 0) {
            setFiles(prev => [...prev, ...filesToAdd]);
        }
    };

    const removeFile = (index: number) => {
        setFiles(prev => prev.filter((_, i) => i !== index));
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);

        if (e.dataTransfer.files) {
            addFiles(Array.from(e.dataTransfer.files));
        }
    }, [files.length]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
    }, []);

    const handleUpload = async () => {
        if (files.length === 0) return;

        setLoading(true);
        setToast(null);

        // Get auth token
        const token = localStorage.getItem('access_token');
        if (!token) {
            setToast({ message: '로그인이 필요합니다.', type: 'error' });
            setLoading(false);
            return;
        }

        const updatedFiles = [...files];

        for (let i = 0; i < updatedFiles.length; i++) {
            if (updatedFiles[i].status !== 'pending') continue;

            updatedFiles[i].status = 'processing';
            setFiles([...updatedFiles]);

            const formData = new FormData();
            formData.append('file', updatedFiles[i].file);

            try {
                const response = await axios.post(apiUrl(`/api/extract?export_format=${exportFormat}`), formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                        'Authorization': `Bearer ${token}`,
                    },
                    timeout: 120000,
                });

                const documentId = response.data.document_id;
                updatedFiles[i].status = 'success';
                updatedFiles[i].downloadUrl = apiUrl(`/api/export/${exportFormat}/${documentId}`);
            } catch (error: any) {
                updatedFiles[i].status = 'error';
                const errorMsg = error.response?.data?.detail || error.message || 'Failed to process';
                updatedFiles[i].error = errorMsg;

                // Show toast for conversion errors
                setToast({ message: `변환 오류: ${errorMsg}`, type: 'error' });
            }

            setFiles([...updatedFiles]);
        }

        setLoading(false);

        // Show success toast if any file succeeded
        const successCount = updatedFiles.filter(f => f.status === 'success').length;
        if (successCount > 0) {
            setToast({ message: `${successCount}개 파일 변환 완료!`, type: 'success' });
        }
    };

    const getFileExtension = (format: ExportFormat): string => {
        switch (format) {
            case 'jsonl': return 'jsonl';
            case 'markdown': return 'md';
            default: return 'txt';
        }
    };

    const downloadFile = async (url: string, filename: string) => {
        try {
            const token = localStorage.getItem('access_token');

            const response = await fetch(url, {
                headers: token ? { 'Authorization': `Bearer ${token}` } : {}
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Download error:', response.status, errorText);
                throw new Error(`Download failed: ${response.status}`);
            }

            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = `${filename}.${getFileExtension(exportFormat)}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(blobUrl);
            document.body.removeChild(a);

            setToast({ message: '다운로드 완료!', type: 'success' });
        } catch (error: any) {
            console.error('Download failed:', error);
            setToast({ message: `다운로드 실패: ${error.message}`, type: 'error' });
        }
    };

    const downloadAll = async () => {
        const successFiles = files.filter(f => f.status === 'success' && f.downloadUrl);
        for (const f of successFiles) {
            await downloadFile(f.downloadUrl!, f.file.name.replace(/\.[^/.]+$/, ''));
            await new Promise(resolve => setTimeout(resolve, 500)); // Small delay between downloads
        }
    };

    const resetAll = () => {
        setFiles([]);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const getFileInfo = (file: File) => {
        const format = SUPPORTED_FORMATS[file.type as keyof typeof SUPPORTED_FORMATS];
        return format || { label: 'File', icon: FileText, color: 'gray' };
    };

    const allCompleted = files.length > 0 && files.every(f => f.status === 'success' || f.status === 'error');
    const hasSuccess = files.some(f => f.status === 'success');
    const hasPending = files.some(f => f.status === 'pending');

    return (
        <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl font-bold mb-2">Upload Documents</h2>
            <p className="text-gray-500 mb-8">Upload up to {MAX_FILES} financial documents for AI-powered distillation</p>

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

                <h3 className="text-xl font-semibold mb-2">Drag and drop your files here</h3>
                <p className="text-gray-500 mb-2">Supported formats:</p>
                <div className="flex flex-wrap justify-center gap-2 mb-4">
                    <span className="px-3 py-1 bg-red-50 text-red-700 rounded-full text-sm font-medium">PDF</span>
                    <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium">Word</span>
                    <span className="px-3 py-1 bg-cyan-50 text-cyan-700 rounded-full text-sm font-medium">HWP</span>
                    <span className="px-3 py-1 bg-green-50 text-green-700 rounded-full text-sm font-medium">Excel</span>
                    <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm font-medium">CSV</span>
                    <span className="px-3 py-1 bg-amber-50 text-amber-700 rounded-full text-sm font-medium">XBRL</span>
                    <span className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm font-medium">Images</span>
                </div>
                <p className="text-sm text-gray-400 mb-6">Maximum {MAX_FILES} files at once • {files.length}/{MAX_FILES} selected</p>

                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                    accept=".pdf,.xlsx,.xls,.csv,.docx,.hwpx,.hwp,.xml,.xbrl,image/*"
                    multiple
                />
                {files.length < MAX_FILES && !allCompleted && (
                    <label
                        htmlFor="file-upload"
                        className="inline-block px-6 py-3 bg-white border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors font-medium text-gray-700"
                    >
                        Select Files
                    </label>
                )}

                {/* File List */}
                {files.length > 0 && (
                    <div className="mt-6 space-y-2">
                        {files.map((fileResult, index) => {
                            const fileInfo = getFileInfo(fileResult.file);
                            return (
                                <div key={index} className="p-3 bg-gray-50 rounded-lg flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg ${fileResult.status === 'success' ? 'bg-green-100' :
                                            fileResult.status === 'error' ? 'bg-red-100' :
                                                fileResult.status === 'processing' ? 'bg-yellow-100' :
                                                    `bg-${fileInfo.color}-100`
                                            }`}>
                                            {fileResult.status === 'success' ? (
                                                <CheckCircle className="w-5 h-5 text-green-600" />
                                            ) : fileResult.status === 'error' ? (
                                                <AlertCircle className="w-5 h-5 text-red-600" />
                                            ) : fileResult.status === 'processing' ? (
                                                <Loader2 className="w-5 h-5 text-yellow-600 animate-spin" />
                                            ) : (
                                                <fileInfo.icon className={`w-5 h-5 text-${fileInfo.color}-600`} />
                                            )}
                                        </div>
                                        <div className="text-left">
                                            <span className="font-medium text-gray-700 block text-sm truncate max-w-[200px]">
                                                {fileResult.file.name}
                                            </span>
                                            <span className="text-xs text-gray-500">
                                                {fileResult.status === 'error' ? fileResult.error :
                                                    fileResult.status === 'processing' ? 'Processing...' :
                                                        fileResult.status === 'success' ? 'Complete' :
                                                            `${(fileResult.file.size / 1024 / 1024).toFixed(2)} MB`}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {fileResult.status === 'success' && fileResult.downloadUrl && (
                                            <button
                                                onClick={() => downloadFile(fileResult.downloadUrl!, fileResult.file.name.replace(/\.[^/.]+$/, ''))}
                                                className="p-1 hover:bg-green-200 rounded-full transition-colors"
                                                title="Download"
                                            >
                                                <Download className="w-4 h-4 text-green-600" />
                                            </button>
                                        )}
                                        {fileResult.status === 'pending' && (
                                            <button
                                                onClick={() => removeFile(index)}
                                                className="p-1 hover:bg-gray-200 rounded-full transition-colors"
                                                title="Remove"
                                            >
                                                <X className="w-4 h-4 text-gray-500" />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Action Buttons */}
                <div className="mt-8">
                    {allCompleted && hasSuccess ? (
                        <div className="space-y-3">
                            <button
                                onClick={downloadAll}
                                className="w-full py-3 rounded-lg font-medium text-white bg-green-600 hover:bg-green-700 shadow-md flex items-center justify-center gap-2"
                            >
                                <Download className="w-5 h-5" />
                                Download All ({files.filter(f => f.status === 'success').length} files)
                            </button>
                            <button
                                onClick={resetAll}
                                className="w-full py-2 rounded-lg font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
                            >
                                Convert New Files
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={handleUpload}
                            disabled={files.length === 0 || loading || !hasPending}
                            className={`w-full py-3 rounded-lg font-medium text-white transition-all flex items-center justify-center gap-2
                                ${files.length === 0 || loading || !hasPending ? 'bg-gray-300 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 shadow-md'}
                            `}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    Processing {files.filter(f => f.status === 'processing').length > 0 ?
                                        `(${files.filter(f => f.status === 'success').length + 1}/${files.length})` : '...'}
                                </>
                            ) : (
                                `Start Distillation (${files.length} file${files.length > 1 ? 's' : ''})`
                            )}
                        </button>
                    )}
                </div>
            </div>

            {/* Export Format Selector */}
            <div className="mt-8">
                <h3 className="text-lg font-semibold mb-3 text-gray-700">Select Export Format</h3>
                <div className="grid grid-cols-2 gap-4">
                    {/* JSONL */}
                    <button
                        onClick={() => setExportFormat('jsonl')}
                        disabled={loading}
                        className={`p-4 rounded-lg text-center transition-all border-2 ${exportFormat === 'jsonl'
                            ? 'bg-purple-100 border-purple-500 shadow-md'
                            : 'bg-purple-50 border-transparent hover:border-purple-300'
                            } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <h4 className={`font-medium ${exportFormat === 'jsonl' ? 'text-purple-800' : 'text-purple-700'}`}>
                            JSONL
                        </h4>
                        {exportFormat === 'jsonl' && (
                            <span className="inline-block mt-1 px-2 py-0.5 bg-purple-500 text-white text-xs rounded-full">✓</span>
                        )}
                    </button>

                    {/* Markdown */}
                    <button
                        onClick={() => setExportFormat('markdown')}
                        disabled={loading}
                        className={`p-4 rounded-lg text-center transition-all border-2 ${exportFormat === 'markdown'
                            ? 'bg-green-100 border-green-500 shadow-md'
                            : 'bg-green-50 border-transparent hover:border-green-300'
                            } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <h4 className={`font-medium ${exportFormat === 'markdown' ? 'text-green-800' : 'text-green-700'}`}>
                            Markdown
                        </h4>
                        {exportFormat === 'markdown' && (
                            <span className="inline-block mt-1 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full">✓</span>
                        )}
                    </button>
                </div>
            </div>

            {/* Toast Notification */}
            {toast && (
                <div
                    className={`fixed bottom-6 right-6 px-6 py-4 rounded-xl shadow-lg flex items-center gap-3 z-50 transition-all ${toast.type === 'success'
                        ? 'bg-green-600 text-white'
                        : 'bg-red-600 text-white'
                        }`}
                >
                    {toast.type === 'success' ? (
                        <CheckCircle className="w-5 h-5" />
                    ) : (
                        <AlertCircle className="w-5 h-5" />
                    )}
                    <span>{toast.message}</span>
                    <button
                        onClick={() => setToast(null)}
                        className="ml-2 hover:opacity-75"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}
        </div>
    );
}

