"use client";

import React, { useState } from 'react';
import { Worker, Viewer, PdfJs, RenderPageProps } from '@react-pdf-viewer/core';

import '@react-pdf-viewer/core/lib/styles/index.css';

interface LineageViewerProps {
    fileUrl: string;
    highlight?: {
        page: number;
        box: [number, number, number, number]; // [x1, y1, x2, y2] in points
    };
}

const LineageViewer: React.FC<LineageViewerProps> = ({ fileUrl, highlight }) => {
    const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);

    const onDocumentLoad = (e: { doc: PdfJs.PdfDocument }) => {
        e.doc.getPage(1).then((page) => {
            const viewport = page.getViewport({ scale: 1 });
            setPageSize({ width: viewport.width, height: viewport.height });
        });
    };

    const renderPage = (props: RenderPageProps) => {
        return (
            <>
                {props.canvasLayer.children}
                {props.textLayer.children}
                {props.annotationLayer.children}
                {highlight && props.pageIndex === highlight.page - 1 && pageSize && (
                    <div
                        style={{
                            background: 'rgba(43, 149, 214, 0.3)',
                            border: '2px solid #2B95D6',
                            left: `${(highlight.box[0] / pageSize.width) * 100}%`,
                            top: `${(highlight.box[1] / pageSize.height) * 100}%`,
                            width: `${((highlight.box[2] - highlight.box[0]) / pageSize.width) * 100}%`,
                            height: `${((highlight.box[3] - highlight.box[1]) / pageSize.height) * 100}%`,
                            position: 'absolute',
                            zIndex: 10,
                            pointerEvents: 'none',
                        }}
                    />
                )}
            </>
        );
    };

    return (
        <div className="h-full w-full bg-[#1a1c1e] border border-[#30404d]">
            <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js">
                <Viewer
                    fileUrl={fileUrl}
                    initialPage={highlight ? highlight.page - 1 : 0}
                    onDocumentLoad={onDocumentLoad}
                    renderPage={renderPage}
                />
            </Worker>
        </div>
    );
};

export default LineageViewer;
