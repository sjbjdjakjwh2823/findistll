'use client';

import { useState, useCallback, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, FileSpreadsheet, Image as ImageIcon, Download, X, ArrowLeft, Cpu, Zap, Activity, Database, Network, ChevronDown, Check } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { apiUrl } from '@/lib/api';

const SUPPORTED_FORMATS: Record<string, { label: string; icon: any; color: string }> = {
    'application/pdf': { label: 'PDF', icon: FileText, color: 'text-red-400' },
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': { label: 'Excel', icon: FileSpreadsheet, color: 'text-green-400' },
    'application/vnd.ms-excel': { label: 'Excel', icon: FileSpreadsheet, color: 'text-green-400' },
    'text/csv': { label: 'CSV', icon: FileSpreadsheet, color: 'text-blue-400' },
    'image/png': { label: 'Image', icon: ImageIcon, color: 'text-purple-400' },
    'image/jpeg': { label: 'Image', icon: ImageIcon, color: 'text-purple-400' },
    'image/webp': { label: 'Image', icon: ImageIcon, color: 'text-purple-400' },
};

interface FileResult {
    file: File;
    status: 'pending' | 'processing' | 'success' | 'error';
    downloadUrl?: string;
    error?: string;
}

const MAX_FILES = 5;

type ExportFormat = 'auto' | 'jsonl' | 'markdown' | 'parquet';
type SpokeType = 'hub' | 'spoke_a' | 'spoke_b' | 'spoke_c' | 'spoke_d';

const SPOKES = [
    { id: 'hub', label: 'Hub: Math Engine', icon: Cpu, desc: 'Zero-copy processing & core math', defaultFormat: 'jsonl' },
    { id: 'spoke_a', label: 'Spoke A: AI Tuning', icon: Zap, desc: 'Chain-of-Thought JSONL generation', defaultFormat: 'jsonl' },
    { id: 'spoke_b', label: 'Spoke B: Quant Data', icon: Activity, desc: 'Z-Ordered Parquet time-series', defaultFormat: 'parquet' },
    { id: 'spoke_c', label: 'Spoke C: RAG Data', icon: Database, desc: 'Context Tree JSON structures', defaultFormat: 'jsonl' },
    { id: 'spoke_d', label: 'Spoke D: Risk Graph', icon: Network, desc: 'Causal Triples JSON mapping', defaultFormat: 'jsonl' },
];

export default function UploadPage() {
    const [files, setFiles] = useState<FileResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [exportFormat, setExportFormat] = useState<ExportFormat>('auto');
    const [isFormatDropdownOpen, setIsFormatDropdownOpen] = useState(false);
    const [selectedSpoke, setSelectedSpoke] = useState<SpokeType>('hub');
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

    const getResolvedFormat = (spokeId: string, format: ExportFormat): string => {
        if (format !== 'auto') return format;
        const spoke = SPOKES.find(s => s.id === spokeId);
        return spoke ? spoke.defaultFormat : 'jsonl';
    };

    const handleUpload = async () => {
        if (files.length === 0) return;

        setLoading(true);
        setToast(null);

        const updatedFiles = [...files];

        for (let i = 0; i < updatedFiles.length; i++) {
            if (updatedFiles[i].status !== 'pending') continue;

            updatedFiles[i].status = 'processing';
            setFiles([...updatedFiles]);

            const formData = new FormData();
            formData.append('file', updatedFiles[i].file);
            formData.append('spoke', selectedSpoke);

            const resolvedFormat = getResolvedFormat(selectedSpoke, exportFormat);

            try {
                const response = await fetch(apiUrl(`/api/extract?export_format=${resolvedFormat}`), {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    let errorMsg = 'Upload failed';
                    try {
                        const errorJson = JSON.parse(errorText);
                        errorMsg = errorJson.detail || errorText;
                    } catch (e) {
                        errorMsg = errorText;
                    }
                    throw new Error(errorMsg);
                }

                const data = await response.json();
                const documentId = data.document_id;
                
                updatedFiles[i].status = 'success';
                updatedFiles[i].downloadUrl = apiUrl(`/api/export/${resolvedFormat}/${documentId}`);
            } catch (error: any) {
                updatedFiles[i].status = 'error';
                updatedFiles[i].error = error.message || 'Failed to process';
                setToast({ message: `Error: ${updatedFiles[i].error}`, type: 'error' });
            }

            setFiles([...updatedFiles]);
        }

        setLoading(false);

        const successCount = updatedFiles.filter(f => f.status === 'success').length;
        if (successCount > 0) {
            setToast({ message: `${successCount} file(s) processed successfully!`, type: 'success' });
        }
    };

    const getFileExtension = (format: string): string => {
        switch (format) {
            case 'jsonl': return 'jsonl';
            case 'markdown': return 'md';
            case 'parquet': return 'parquet';
            default: return 'txt';
        }
    };

    const downloadFile = async (url: string, filename: string) => {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Download failed: ${response.status}`);

            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            
            const resolvedFormat = getResolvedFormat(selectedSpoke, exportFormat);
            a.download = `${filename}.${getFileExtension(resolvedFormat)}`;
            
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(blobUrl);
            document.body.removeChild(a);

            setToast({ message: 'Download complete!', type: 'success' });
        } catch (error: any) {
            setToast({ message: `Download failed: ${error.message}`, type: 'error' });
        }
    };

    const downloadAll = async () => {
        const successFiles = files.filter(f => f.status === 'success' && f.downloadUrl);
        for (const f of successFiles) {
            await downloadFile(f.downloadUrl!, f.file.name.replace(/\.[^/.]+$/, ''));
            await new Promise(resolve => setTimeout(resolve, 500));
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
        return format || { label: 'File', icon: FileText, color: 'text-gray-400' };
    };

    const allCompleted = files.length > 0 && files.every(f => f.status === 'success' || f.status === 'error');
    const hasSuccess = files.some(f => f.status === 'success');
    const hasPending = files.some(f => f.status === 'pending');

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-gray-200">
            <div className="fixed inset-0 bg-grid-pattern opacity-20 pointer-events-none"></div>
            <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-purple-900/20 blur-[100px] pointer-events-none rounded-full"></div>

            <nav className="border-b border-white/5 bg-black/50 backdrop-blur-md sticky top-0 z-50">
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                    <button 
                        onClick={() => router.back()}
                        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors group"
                    >
                        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
                        Back to Home
                    </button>
                    <div className="text-sm font-medium tracking-widest uppercase text-white/50">
                        Pipeline Configuration
                    </div>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto px-6 py-12 relative z-10">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
                    
                    <div className="lg:col-span-5 space-y-8">
                        <div>
                            <h1 className="text-3xl font-bold text-white mb-2">Ingestion Engine</h1>
                            <p className="text-gray-500">Configure your data processing pipeline and target spoke.</p>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Target Spoke</h3>
                            <div className="space-y-3">
                                {SPOKES.map((spoke) => {
                                    const Icon = spoke.icon;
                                    const isSelected = selectedSpoke === spoke.id;
                                    return (
                                        <button
                                            key={spoke.id}
                                            onClick={() => setSelectedSpoke(spoke.id as SpokeType)}
                                            className={`w-full text-left p-4 rounded-xl border transition-all duration-200 group relative overflow-hidden
                                                ${isSelected 
                                                    ? 'bg-purple-500/10 border-purple-500/50 shadow-[0_0_20px_rgba(168,85,247,0.15)]' 
                                                    : 'bg-white/5 border-white/10 hover:border-white/20 hover:bg-white/10'
                                                }
                                            `}
                                        >
                                            <div className="flex items-start gap-4 relative z-10">
                                                <div className={`p-2 rounded-lg ${isSelected ? 'bg-purple-500 text-white' : 'bg-white/10 text-gray-400'}`}>
                                                    <Icon className="w-5 h-5" />
                                                </div>
                                                <div>
                                                    <div className={`font-medium ${isSelected ? 'text-white' : 'text-gray-300'}`}>
                                                        {spoke.label}
                                                    </div>
                                                    <div className="text-xs text-gray-500 mt-1">
                                                        {spoke.desc}
                                                    </div>
                                                </div>
                                                {isSelected && (
                                                    <div className="absolute right-0 top-1/2 -translate-y-1/2 text-purple-400">
                                                        <CheckCircle className="w-5 h-5" />
                                                    </div>
                                                )}
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Output Format</h3>
                            <div className="relative">
                                <button
                                    onClick={() => setIsFormatDropdownOpen(!isFormatDropdownOpen)}
                                    className="w-full p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-all flex items-center justify-between group"
                                >
                                    <div className="flex flex-col items-start">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-white">
                                                {exportFormat === 'auto' ? 'Native (Auto-Optimized)' : 
                                                 exportFormat === 'jsonl' ? 'JSONL (Structured)' :
                                                 exportFormat === 'markdown' ? 'Markdown (Readable)' : 'Parquet'}
                                            </span>
                                            {exportFormat === 'auto' && (
                                                <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                                    Recommended
                                                </span>
                                            )}
                                        </div>
                                        <span className="text-xs text-gray-500 mt-1">
                                            {exportFormat === 'auto' 
                                                ? `Automatically selects ${SPOKES.find(s => s.id === selectedSpoke)?.defaultFormat.toUpperCase()}` 
                                                : exportFormat === 'jsonl' ? 'Best for LLM Fine-tuning'
                                                : 'Best for RAG & Documentation'}
                                        </span>
                                    </div>
                                    <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${isFormatDropdownOpen ? 'rotate-180' : ''}`} />
                                </button>

                                {isFormatDropdownOpen && (
                                    <div className="absolute top-full left-0 right-0 mt-2 bg-[#111] border border-white/10 rounded-xl shadow-xl overflow-hidden z-20 animate-in fade-in zoom-in-95 duration-200">
                                        <button
                                            onClick={() => { setExportFormat('auto'); setIsFormatDropdownOpen(false); }}
                                            className="w-full p-4 text-left hover:bg-white/5 flex items-center justify-between group transition-colors"
                                        >
                                            <div>
                                                <div className="font-medium text-white group-hover:text-purple-400 transition-colors">Native (Auto-Optimized)</div>
                                                <div className="text-xs text-gray-500">Best for selected Spoke engine</div>
                                            </div>
                                            {exportFormat === 'auto' && <Check className="w-4 h-4 text-purple-400" />}
                                        </button>
                                        <button
                                            onClick={() => { setExportFormat('jsonl'); setIsFormatDropdownOpen(false); }}
                                            className="w-full p-4 text-left hover:bg-white/5 flex items-center justify-between group transition-colors border-t border-white/5"
                                        >
                                            <div>
                                                <div className="font-medium text-white group-hover:text-purple-400 transition-colors">JSONL</div>
                                                <div className="text-xs text-gray-500">Structured data for AI training</div>
                                            </div>
                                            {exportFormat === 'jsonl' && <Check className="w-4 h-4 text-purple-400" />}
                                        </button>
                                        <button
                                            onClick={() => { setExportFormat('markdown'); setIsFormatDropdownOpen(false); }}
                                            className="w-full p-4 text-left hover:bg-white/5 flex items-center justify-between group transition-colors border-t border-white/5"
                                        >
                                            <div>
                                                <div className="font-medium text-white group-hover:text-purple-400 transition-colors">Markdown</div>
                                                <div className="text-xs text-gray-500">Human readable documentation</div>
                                            </div>
                                            {exportFormat === 'markdown' && <Check className="w-4 h-4 text-purple-400" />}
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="lg:col-span-7">
                        <div 
                            className={`h-full min-h-[500px] rounded-2xl border-2 border-dashed transition-all duration-300 relative overflow-hidden flex flex-col
                                ${dragOver 
                                    ? 'border-purple-500 bg-purple-500/5' 
                                    : 'border-white/10 bg-[#111]'
                                }
                            `}
                            onDrop={handleDrop}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                        >
                            {files.length === 0 ? (
                                <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
                                    <div className={`w-20 h-20 rounded-2xl flex items-center justify-center mb-6 transition-all duration-300
                                        ${dragOver ? 'bg-purple-500/20 scale-110' : 'bg-white/5'}
                                    `}>
                                        <Upload className={`w-10 h-10 ${dragOver ? 'text-purple-400' : 'text-gray-500'}`} />
                                    </div>
                                    <h3 className="text-xl font-medium text-white mb-2">
                                        Drop financial documents here
                                    </h3>
                                    <p className="text-gray-500 mb-8 max-w-sm">
                                        Support for PDF, Excel, CSV, XBRL, and scanned images. Up to {MAX_FILES} files allowed.
                                    </p>
                                    
                                    <input
                                        type="file"
                                        ref={fileInputRef}
                                        onChange={handleFileChange}
                                        className="hidden"
                                        id="file-upload"
                                        accept=".pdf,.xlsx,.xls,.csv,.docx,.hwpx,.hwp,.xml,.xbrl,image/*"
                                        multiple
                                    />
                                    <label
                                        htmlFor="file-upload"
                                        className="px-8 py-4 bg-white text-black rounded-lg font-semibold hover:bg-gray-200 transition-colors cursor-pointer"
                                    >
                                        Select Files
                                    </label>
                                </div>
                            ) : (
                                <div className="flex-1 flex flex-col p-6">
                                    <div className="flex-1 space-y-3 overflow-y-auto mb-6 custom-scrollbar">
                                        {files.map((fileResult, index) => {
                                            const fileInfo = getFileInfo(fileResult.file);
                                            const Icon = fileInfo.icon;
                                            return (
                                                <div key={index} className="p-4 rounded-xl bg-white/5 border border-white/10 flex items-center justify-between group">
                                                    <div className="flex items-center gap-4">
                                                        <div className={`p-2.5 rounded-lg bg-black/30 border border-white/5 ${fileInfo.color}`}>
                                                            <Icon className="w-5 h-5" />
                                                        </div>
                                                        <div>
                                                            <div className="text-sm font-medium text-gray-200 truncate max-w-[200px] sm:max-w-[300px]">
                                                                {fileResult.file.name}
                                                            </div>
                                                            <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                                                                <span>{(fileResult.file.size / 1024 / 1024).toFixed(2)} MB</span>
                                                                <span className="w-1 h-1 rounded-full bg-gray-700"></span>
                                                                <span className={
                                                                    fileResult.status === 'error' ? 'text-red-400' :
                                                                    fileResult.status === 'success' ? 'text-green-400' :
                                                                    fileResult.status === 'processing' ? 'text-yellow-400' :
                                                                    'text-gray-500'
                                                                }>
                                                                    {fileResult.status === 'processing' ? 'Processing...' : 
                                                                     fileResult.status === 'success' ? 'Ready' : 
                                                                     fileResult.status === 'error' ? 'Failed' : 'Pending'}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    <div className="flex items-center gap-2">
                                                        {fileResult.status === 'success' && fileResult.downloadUrl && (
                                                            <button
                                                                onClick={() => downloadFile(fileResult.downloadUrl!, fileResult.file.name.replace(/\.[^/.]+$/, ''))}
                                                                className="p-2 hover:bg-green-500/20 text-green-400 rounded-lg transition-colors"
                                                            >
                                                                <Download className="w-4 h-4" />
                                                            </button>
                                                        )}
                                                        {fileResult.status === 'pending' && (
                                                            <button
                                                                onClick={() => removeFile(index)}
                                                                className="p-2 hover:bg-white/10 text-gray-500 hover:text-white rounded-lg transition-colors"
                                                            >
                                                                <X className="w-4 h-4" />
                                                            </button>
                                                        )}
                                                        {fileResult.status === 'processing' && (
                                                            <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>

                                    <div className="pt-6 border-t border-white/10">
                                        {allCompleted && hasSuccess ? (
                                            <div className="grid grid-cols-2 gap-4">
                                                <button
                                                    onClick={resetAll}
                                                    className="px-6 py-4 rounded-xl font-medium text-gray-300 bg-white/5 hover:bg-white/10 transition-colors border border-white/10"
                                                >
                                                    Process More
                                                </button>
                                                <button
                                                    onClick={downloadAll}
                                                    className="px-6 py-4 rounded-xl font-medium text-black bg-white hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
                                                >
                                                    <Download className="w-5 h-5" />
                                                    Download All
                                                </button>
                                            </div>
                                        ) : (
                                            <button
                                                onClick={handleUpload}
                                                disabled={files.length === 0 || loading || !hasPending}
                                                className={`w-full py-4 rounded-xl font-semibold text-white transition-all flex items-center justify-center gap-2
                                                    ${files.length === 0 || loading || !hasPending 
                                                        ? 'bg-white/5 text-gray-500 cursor-not-allowed border border-white/5' 
                                                        : 'bg-purple-600 hover:bg-purple-500 shadow-lg shadow-purple-900/20'
                                                    }
                                                `}
                                            >
                                                {loading ? (
                                                    <>
                                                        <Loader2 className="w-5 h-5 animate-spin" />
                                                        Initialize Pipeline...
                                                    </>
                                                ) : (
                                                    `Start Ingestion Protocol`
                                                )}
                                            </button>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {toast && (
                    <div className={`fixed bottom-8 right-8 px-6 py-4 rounded-xl shadow-2xl flex items-center gap-4 z-50 border backdrop-blur-xl animate-in fade-in slide-in-from-bottom-5
                        ${toast.type === 'success' 
                            ? 'bg-green-500/10 border-green-500/20 text-green-400' 
                            : 'bg-red-500/10 border-red-500/20 text-red-400'
                        }
                    `}>
                        {toast.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                        <span className="font-medium">{toast.message}</span>
                        <button onClick={() => setToast(null)} className="ml-2 hover:opacity-75">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                )}
            </main>
        </div>
    );
}
