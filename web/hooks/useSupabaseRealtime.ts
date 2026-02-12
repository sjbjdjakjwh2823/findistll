import { useEffect, useState } from "react";
import { supabaseClient } from "../lib/supabaseClient";

export type RealtimeRecord = { id?: string | number } & Record<string, unknown>;

type UseSupabaseRealtimeResult<T extends RealtimeRecord> = {
  data: T[];
  loading: boolean;
  status: "idle" | "connecting" | "connected" | "error";
};

type UseSupabaseRealtimeOptions = {
  table?: string;
  fetchInitial?: boolean;
};

export function useSupabaseRealtime<T extends RealtimeRecord = RealtimeRecord>(
  options: UseSupabaseRealtimeOptions = {}
): UseSupabaseRealtimeResult<T> {
  const table = options.table ?? "cases";
  const fetchInitial = options.fetchInitial ?? true;
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<UseSupabaseRealtimeResult<T>["status"]>("idle");

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setStatus("connecting");
      setLoading(true);
      if (!fetchInitial) {
        setLoading(false);
        return;
      }
      const { data, error } = await supabaseClient.from(table).select("*");
      if (!mounted) return;
      if (!error && data) {
        setData(data as T[]);
      } else if (error) {
        setStatus("error");
      }
      setLoading(false);
    };

    load();

    const channel = supabaseClient
      .channel(`${table}-realtime`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table },
        (payload) => {
          setData((current) => {
            const newRow = payload.new as T;
            const oldRow = payload.old as T;

            if (payload.eventType === "INSERT") {
              return [...current, newRow];
            }

            if (payload.eventType === "UPDATE") {
              return current.map((row) =>
                row.id === newRow.id ? newRow : row
              );
            }

            if (payload.eventType === "DELETE") {
              return current.filter((row) => row.id !== oldRow.id);
            }

            return current;
          });
        }
      )
      .subscribe((subStatus) => {
        if (!mounted) return;
        if (subStatus === "SUBSCRIBED") {
          setStatus("connected");
        } else if (subStatus === "CHANNEL_ERROR") {
          setStatus("error");
        } else {
          setStatus("connecting");
        }
      });

    return () => {
      mounted = false;
      supabaseClient.removeChannel(channel);
    };
  }, [table, fetchInitial]);

  return { data, loading, status };
}
