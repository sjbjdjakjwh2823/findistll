'use client';

import { useState } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { apiUrl } from '@/lib/api';

export default function UploadPage() {
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const router = useRouter();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setLoading(true);
        setStatus('idle');

        const formData = new FormData();
        formData.append('file', file);

        try {
            await axios.post(apiUrl('/api/extract'), formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setStatus('success');
            setTimeout(() => router.push('/history'), 1500);
        } catch (error) {
            console.error(error);
            setStatus('error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl font-bold mb-8">Upload Document</h2>

            <div className="bg-white p-12 rounded-xl shadow-sm border border-gray-200 text-center">
                <div className="mb-8 flex justify-center">
                    <div className="w-20 h-20 bg-blue-50 rounded-full flex items-center justify-center">
                        <Upload className="w-10 h-10 text-blue-600" />
                    </div>
                </div>

                <h3 className="text-xl font-semibold mb-2">Drag and drop your file here</h3>
                <p className="text-gray-500 mb-8">Supported formats: PDF, Images (Max 10MB)</p>

                <input
                    type="file"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                    accept=".pdf,image/*"
                />
                <label
                    htmlFor="file-upload"
                    className="inline-block px-6 py-3 bg-white border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors font-medium text-gray-700"
                >
                    Select File
                </label>

                {file && (
                    <div className="mt-6 p-4 bg-gray-50 rounded-lg flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <FileText className="w-5 h-5 text-gray-500" />
                            <span className="font-medium text-gray-700">{file.name}</span>
                        </div>
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
                                Processing...
                            </>
                        ) : (
                            'Start Extraction'
                        )}
                    </button>
                </div>

                {status === 'success' && (
                    <div className="mt-4 p-4 bg-green-50 text-green-700 rounded-lg flex items-center gap-2 justify-center">
                        <CheckCircle className="w-5 h-5" />
                        Extraction complete! Redirecting...
                    </div>
                )}

                {status === 'error' && (
                    <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-lg flex items-center gap-2 justify-center">
                        <AlertCircle className="w-5 h-5" />
                        Failed to process document. Please try again.
                    </div>
                )}
            </div>
        </div>
    );
}
