import React from "react";

export interface ExtractedFact {
  id: string;
  category: string;
  key: string;
  value: string | number;
  unit: string;
  source_document: string;
  source_page: number;
  confidence: number;
}

export function ExtractedFactsTable({ facts }: { facts: ExtractedFact[] }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/40 p-4">
      <div className="text-xs text-neutral-500 mb-2">Extracted Facts</div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-neutral-200">
          <thead className="text-[11px] text-neutral-500">
            <tr>
              <th className="text-left py-2">Category</th>
              <th className="text-left py-2">Key</th>
              <th className="text-left py-2">Value</th>
              <th className="text-left py-2">Unit</th>
              <th className="text-left py-2">Source</th>
              <th className="text-left py-2">Conf.</th>
            </tr>
          </thead>
          <tbody>
            {facts.length === 0 && (
              <tr>
                <td colSpan={6} className="py-3 text-neutral-500">
                  No facts extracted yet.
                </td>
              </tr>
            )}
            {facts.map((fact) => (
              <tr key={fact.id} className="border-t border-white/5">
                <td className="py-2">{fact.category}</td>
                <td className="py-2">{fact.key}</td>
                <td className="py-2">{fact.value}</td>
                <td className="py-2">{fact.unit}</td>
                <td className="py-2 text-neutral-400">
                  {fact.source_document} · p{fact.source_page}
                </td>
                <td className="py-2">{Math.round(fact.confidence * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
