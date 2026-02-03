import React from "react";
import CaseDetailClient from "./CaseDetailClient";

export function generateStaticParams() {
  return [{ id: 'sample-case' }];
}

export const dynamic = 'force-static';
export const dynamicParams = false;

export default async function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CaseDetailClient id={id} />;
}
