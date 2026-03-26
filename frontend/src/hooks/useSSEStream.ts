"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, useAuthStore } from "@/store/authStore";
import type { CasoResumen } from "@/types/api";

export interface TicketBoard {
  id: string;
  cedula: string;
  tipo: string;
  subject: string;
  client: string;
  clienteId: string;
  clienteNombre: string;
  severity: string;
  status: string;
  source: string;
  date: string;
  vencimientoRaw: string | null;
}

interface TutelaUrgentePayload {
  caso_id: string;
  asunto: string;
}

interface UseSSEStreamOptions {
  onTutelaUrgente?: (data: TutelaUrgentePayload) => void;
}

function mapCasoToTicket(c: CasoResumen): TicketBoard {
  const docMatch = c.asunto?.match(/Doc:\s*(\d+)/i) || c.asunto?.match(/(\d{7,10})/);
  return {
    id: c.id,
    cedula: docMatch ? docMatch[1] : "S/N",
    tipo: c.tipo,
    subject: c.asunto,
    client: c.email,
    clienteId: c.cliente_id || "",
    clienteNombre: c.cliente_nombre || "—",
    severity: c.prioridad,
    status: c.estado,
    source: c.tipo === "TUTELA" ? "TUTELA - Juzgado" : "PQR",
    date: c.fecha ? new Date(c.fecha).toLocaleDateString() : "",
    vencimientoRaw: c.vencimiento,
  };
}

const RECONNECT_DELAYS = [2000, 4000, 8000];

export function useSSEStream(options?: UseSSEStreamOptions) {
  const [tickets, setTickets] = useState<TicketBoard[]>([]);
  const [connected, setConnected] = useState(false);
  const token = useAuthStore((s) => s.token);

  // Refs para evitar memory leaks en reconexión
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  // Ref estable para el callback, evita re-renders del useEffect
  const onTutelaUrgenteRef = useRef(options?.onTutelaUrgente);
  useEffect(() => {
    onTutelaUrgenteRef.current = options?.onTutelaUrgente;
  }, [options?.onTutelaUrgente]);

  useEffect(() => {
    if (!token) return;

    api
      .get("/stats/dashboard")
      .then((res) => {
        if (res.data?.ultimos_casos) {
          setTickets(res.data.ultimos_casos.map(mapCasoToTicket));
        }
      })
      .catch(console.error);

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

    function conectar() {
      // Cierra conexión previa si existe antes de abrir una nueva
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const es = new EventSource(`${baseUrl}/api/v2/stream/listen?token=${token}`);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        reconnectAttemptRef.current = 0;
      };

      es.addEventListener("new_pqr", (event) => {
        try {
          const data = JSON.parse(event.data) as {
            id?: string;
            caso_id?: string;
            tipo?: string;
            tipo_caso?: string;
            subject?: string;
            asunto?: string;
            email?: string;
            cliente_id?: string;
            cliente_nombre?: string;
            prioridad?: string;
            estado?: string;
            vencimiento?: string;
          };

          const resolvedId = data.caso_id ?? data.id ?? "";
          const resolvedTipo = data.tipo_caso ?? data.tipo ?? "";
          const resolvedAsunto = data.asunto ?? data.subject ?? "";

          const docMatch =
            resolvedAsunto.match(/Doc:\s*(\d+)/i) ||
            resolvedAsunto.match(/(\d{7,10})/);

          const ticket: TicketBoard = {
            id: resolvedId,
            cedula: docMatch ? docMatch[1] : "S/N",
            tipo: resolvedTipo,
            subject: resolvedAsunto,
            client: data.email ?? "",
            clienteId: data.cliente_id ?? "",
            clienteNombre: data.cliente_nombre ?? "—",
            severity: data.prioridad ?? "",
            status: data.estado ?? "",
            source: resolvedTipo === "TUTELA" ? "TUTELA - Juzgado" : "PQR",
            date: new Date().toLocaleDateString(),
            vencimientoRaw: data.vencimiento ?? null,
          };

          setTickets((prev) => [ticket, ...prev]);

          if (resolvedTipo === "TUTELA" && data.prioridad === "CRITICA") {
            onTutelaUrgenteRef.current?.({
              caso_id: resolvedId,
              asunto: resolvedAsunto || "Tutela urgente",
            });
          }
        } catch (err) {
          console.error("Error parseando SSE:", err);
        }
      });

      // Ignorar pings del servidor sin loguear como error
      es.addEventListener("ping", () => {});

      es.onerror = () => {
        es.close();
        setConnected(false);

        const delay =
          RECONNECT_DELAYS[
            Math.min(reconnectAttemptRef.current, RECONNECT_DELAYS.length - 1)
          ];
        reconnectAttemptRef.current += 1;

        reconnectTimerRef.current = setTimeout(conectar, delay);
      };
    }

    conectar();

    return () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setConnected(false);
      reconnectAttemptRef.current = 0;
    };
  }, [token]);

  const removeTicket = useCallback((id: string) => {
    setTickets((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { tickets, connected, removeTicket };
}
