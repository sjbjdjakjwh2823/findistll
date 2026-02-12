export type JsonRecord = Record<string, unknown>;

export type ApiList<T = JsonRecord> = {
  items?: T[];
  [key: string]: unknown;
};

export type ApiResult<T = JsonRecord> = T & {
  [key: string]: unknown;
};
