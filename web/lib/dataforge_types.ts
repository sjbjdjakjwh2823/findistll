import type { JsonRecord } from "@/lib/types";

export interface Sample {
  id: string;
  template_type: string;
  generated_content: JsonRecord | string | number | boolean | null;
  confidence_score: number;
  raw_documents?: {
    source: string;
    ticker: string;
    raw_content: JsonRecord | string | null;
  };
}

