import { useCallback, useEffect, useRef, useState } from 'react';

// ============================================================================
// Types
// ============================================================================

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

export interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  /** Full WebSocket URL (e.g. ws://localhost:8001/ws/events) */
  url: string;
  /** Whether to automatically connect on mount */
  autoConnect?: boolean;
  /** Handler for incoming messages */
  onMessage?: (message: WebSocketMessage) => void;
  /** Handler for connection open */
  onOpen?: () => void;
  /** Handler for connection close */
  onClose?: (code: number, reason: string) => void;
  /** Handler for errors */
  onError?: (error: Event) => void;
  /** Ping interval in ms (default: 30000) */
  pingInterval?: number;
  /** Max reconnect attempts (default: 10, 0 = no reconnect) */
  maxReconnectAttempts?: number;
  /** Base reconnect delay in ms (default: 1000, uses exponential backoff) */
  reconnectDelay?: number;
}

interface UseWebSocketReturn {
  /** Current connection state */
  state: ConnectionState;
  /** Send a JSON message */
  send: (message: WebSocketMessage) => void;
  /** Connect manually */
  connect: () => void;
  /** Disconnect manually */
  disconnect: () => void;
  /** Last error message, if any */
  error: string | null;
}

// ============================================================================
// WebSocket URL Helper
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

/** Derive WebSocket base URL from the HTTP API URL. */
function getWsBaseUrl(): string {
  try {
    const url = new URL(API_BASE_URL);
    const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${url.host}`;
  } catch {
    return 'ws://localhost:8001';
  }
}

export const WS_BASE_URL = getWsBaseUrl();

// ============================================================================
// Base Hook
// ============================================================================

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    autoConnect = true,
    onMessage,
    onOpen,
    onClose,
    onError,
    pingInterval = 30000,
    maxReconnectAttempts = 10,
    reconnectDelay = 1000,
  } = options;

  const [state, setState] = useState<ConnectionState>('disconnected');
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const connectWsRef = useRef<() => void>(() => {});

  // Store latest callbacks in refs to avoid reconnect on callback identity change
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;
  });

  const clearTimers = useCallback(() => {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current);
      pingTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const startPing = useCallback(() => {
    if (pingTimerRef.current) clearInterval(pingTimerRef.current);
    pingTimerRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, pingInterval);
  }, [pingInterval]);

  const scheduleReconnect = useCallback(() => {
    if (
      intentionalCloseRef.current ||
      maxReconnectAttempts === 0 ||
      reconnectAttemptsRef.current >= maxReconnectAttempts
    ) {
      setState('disconnected');
      return;
    }

    setState('reconnecting');
    const delay = Math.min(
      reconnectDelay * Math.pow(2, reconnectAttemptsRef.current),
      30000, // cap at 30s
    );
    reconnectAttemptsRef.current += 1;

    reconnectTimerRef.current = setTimeout(() => {
      connectWsRef.current();
    }, delay);
  }, [maxReconnectAttempts, reconnectDelay]);

  const connectWs = useCallback(() => {
    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent reconnect loop
      wsRef.current.close();
      wsRef.current = null;
    }

    clearTimers();
    setError(null);
    setState('connecting');
    intentionalCloseRef.current = false;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setState('connected');
      reconnectAttemptsRef.current = 0;
      startPing();
      onOpenRef.current?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WebSocketMessage;
        // Silently handle pong
        if (data.type === 'pong') return;
        // Handle error messages from server
        if (data.type === 'error') {
          setError((data.message as string) || (data.code as string) || 'Unknown error');
        }
        onMessageRef.current?.(data);
      } catch {
        // Non-JSON message, ignore
      }
    };

    ws.onclose = (event) => {
      clearTimers();
      wsRef.current = null;
      onCloseRef.current?.(event.code, event.reason);

      // Don't reconnect on intentional close or auth failures
      if (
        intentionalCloseRef.current ||
        event.code === 4001 || // token expired
        event.code === 4003 || // origin not allowed
        event.code === 4029 || // connection limit
        event.code === 1008    // policy violation (no auth)
      ) {
        setState('disconnected');
        if (event.code === 4001) {
          setError('Session expired. Please log in again.');
          window.dispatchEvent(new CustomEvent('auth:logout'));
        }
        return;
      }

      scheduleReconnect();
    };

    ws.onerror = (event) => {
      setError('WebSocket connection error');
      onErrorRef.current?.(event);
    };
  }, [url, clearTimers, startPing, scheduleReconnect]);
  useEffect(() => {
    connectWsRef.current = connectWs;
  });

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearTimers();
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }
    setState('disconnected');
  }, [clearTimers]);

  // Auto-connect on mount (deferred to avoid synchronous setState in effect body)
  useEffect(() => {
    if (!autoConnect) return;
    const timer = setTimeout(connectWs, 0);
    return () => clearTimeout(timer);
  }, [autoConnect, connectWs]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      clearTimers();
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close(1000, 'Component unmount');
        wsRef.current = null;
      }
    };
  }, [clearTimers]);

  return { state, send, connect: connectWs, disconnect, error };
}

// ============================================================================
// Event Stream Hook
// ============================================================================

interface EventStreamMessage extends WebSocketMessage {
  type: 'connected' | 'event' | 'subscribed' | 'unsubscribed' | 'error';
}

interface UseEventStreamOptions {
  /** Initial topics to subscribe to */
  topics?: string[];
  /** Called when an event is received */
  onEvent?: (eventType: string, data: Record<string, unknown>, timestamp: string) => void;
  /** Called when subscription changes are confirmed */
  onSubscriptionChange?: (allTopics: string[]) => void;
  /** Whether to auto-connect */
  enabled?: boolean;
}

export function useEventStream(options: UseEventStreamOptions = {}) {
  const { topics = [], onEvent, onSubscriptionChange, enabled = true } = options;
  const onEventRef = useRef(onEvent);
  const onSubChangeRef = useRef(onSubscriptionChange);
  useEffect(() => {
    onEventRef.current = onEvent;
    onSubChangeRef.current = onSubscriptionChange;
  });

  const [subscriptions, setSubscriptions] = useState<string[]>([]);

  const topicsParam = topics.length > 0 ? `?topics=${topics.join(',')}` : '';
  const wsUrl = `${WS_BASE_URL}/ws/events${topicsParam}`;

  const handleMessage = useCallback((msg: WebSocketMessage) => {
    const m = msg as EventStreamMessage;
    switch (m.type) {
      case 'connected':
        setSubscriptions((m.subscriptions as string[]) || []);
        break;
      case 'event':
        onEventRef.current?.(
          m.event_type as string,
          m.data as Record<string, unknown>,
          m.timestamp as string,
        );
        break;
      case 'subscribed':
      case 'unsubscribed':
        setSubscriptions((m.all_subscriptions as string[]) || []);
        onSubChangeRef.current?.((m.all_subscriptions as string[]) || []);
        break;
    }
  }, []);

  const ws = useWebSocket({
    url: wsUrl,
    autoConnect: enabled,
    onMessage: handleMessage,
  });

  const subscribe = useCallback(
    (newTopics: string[]) => ws.send({ type: 'subscribe', topics: newTopics }),
    [ws],
  );

  const unsubscribe = useCallback(
    (removeTopics: string[]) => ws.send({ type: 'unsubscribe', topics: removeTopics }),
    [ws],
  );

  return { ...ws, subscriptions, subscribe, unsubscribe };
}

// ============================================================================
// Dashboard Metrics Hook
// ============================================================================

interface UseDashboardOptions {
  /** Called when metrics update is received */
  onMetrics?: (metrics: Record<string, unknown>, timestamp: string) => void;
  /** Whether to auto-connect */
  enabled?: boolean;
}

export function useDashboardMetrics(options: UseDashboardOptions = {}) {
  const { onMetrics, enabled = true } = options;
  const onMetricsRef = useRef(onMetrics);
  useEffect(() => {
    onMetricsRef.current = onMetrics;
  });

  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const handleMessage = useCallback((msg: WebSocketMessage) => {
    if (msg.type === 'metrics_update') {
      const m = msg.metrics as Record<string, unknown>;
      const ts = msg.timestamp as string;
      setMetrics(m);
      setLastUpdated(ts);
      onMetricsRef.current?.(m, ts);
    }
  }, []);

  const ws = useWebSocket({
    url: `${WS_BASE_URL}/ws/dashboard`,
    autoConnect: enabled,
    onMessage: handleMessage,
  });

  const requestMetrics = useCallback(
    () => ws.send({ type: 'request_metrics' }),
    [ws],
  );

  return { ...ws, metrics, lastUpdated, requestMetrics };
}

// ============================================================================
// Chat Room Hook
// ============================================================================

export interface ChatMessage {
  message_id: string;
  user_id: string;
  display_name?: string;
  content: string;
  timestamp: string;
}

export interface ChatParticipant {
  user_id: string;
  display_name: string;
  role?: string;
}

interface RoomInfo {
  room_id: string;
  name: string;
  description?: string;
  visibility: string;
  role: string | null;
  owner_id: string;
  member_count: number;
  is_archived: boolean;
}

interface UseChatRoomOptions {
  roomId: string;
  displayName?: string;
  inviteCode?: string;
  onMessage?: (message: ChatMessage) => void;
  onUserJoined?: (userId: string, displayName: string, role: string) => void;
  onUserLeft?: (userId: string) => void;
  onTyping?: (userId: string, displayName: string) => void;
  enabled?: boolean;
}

export function useChatRoom(options: UseChatRoomOptions) {
  const {
    roomId,
    displayName,
    inviteCode,
    onMessage: onChatMessage,
    onUserJoined,
    onUserLeft,
    onTyping,
    enabled = true,
  } = options;

  const onChatRef = useRef(onChatMessage);
  const onJoinRef = useRef(onUserJoined);
  const onLeaveRef = useRef(onUserLeft);
  const onTypingRef = useRef(onTyping);
  useEffect(() => {
    onChatRef.current = onChatMessage;
    onJoinRef.current = onUserJoined;
    onLeaveRef.current = onUserLeft;
    onTypingRef.current = onTyping;
  });

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [participants, setParticipants] = useState<ChatParticipant[]>([]);
  const [roomInfo, setRoomInfo] = useState<RoomInfo | null>(null);

  // Reset state when room changes (render-phase adjustment per React docs)
  const [prevRoomId, setPrevRoomId] = useState(roomId);
  if (roomId !== prevRoomId) {
    setPrevRoomId(roomId);
    setMessages([]);
    setParticipants([]);
    setRoomInfo(null);
  }

  // Build URL with query params
  const params = new URLSearchParams();
  if (displayName) params.set('display_name', displayName);
  if (inviteCode) params.set('invite_code', inviteCode);
  const queryStr = params.toString();
  const wsUrl = `${WS_BASE_URL}/ws/chat/${roomId}${queryStr ? `?${queryStr}` : ''}`;

  const handleMessage = useCallback((msg: WebSocketMessage) => {
    const data = msg.data as Record<string, unknown> | undefined;

    switch (msg.type) {
      case 'room_info':
        if (data) setRoomInfo(data as unknown as RoomInfo);
        break;

      case 'participants':
        if (data) setParticipants((data.users as ChatParticipant[]) || []);
        break;

      case 'message': {
        const chatMsg = data as unknown as ChatMessage;
        if (chatMsg) {
          setMessages((prev) => [...prev, chatMsg]);
          onChatRef.current?.(chatMsg);
        }
        break;
      }

      case 'user_joined':
        if (data) {
          const joined: ChatParticipant = {
            user_id: data.user_id as string,
            display_name: data.display_name as string,
            role: data.role as string,
          };
          setParticipants((prev) => [...prev.filter((p) => p.user_id !== joined.user_id), joined]);
          onJoinRef.current?.(joined.user_id, joined.display_name, joined.role || 'member');
        }
        break;

      case 'user_left':
        if (data) {
          const leftId = data.user_id as string;
          setParticipants((prev) => prev.filter((p) => p.user_id !== leftId));
          onLeaveRef.current?.(leftId);
        }
        break;

      case 'message_deleted':
        if (data) {
          const deletedId = data.message_id as string;
          setMessages((prev) => prev.filter((m) => m.message_id !== deletedId));
        }
        break;

      case 'typing':
        if (data) {
          onTypingRef.current?.(data.user_id as string, data.display_name as string);
        }
        break;
    }
  }, []);

  const ws = useWebSocket({
    url: wsUrl,
    autoConnect: enabled && !!roomId,
    onMessage: handleMessage,
  });

  const sendMessage = useCallback(
    (content: string) => ws.send({ type: 'message', content }),
    [ws],
  );

  const sendTyping = useCallback(
    () => ws.send({ type: 'typing' }),
    [ws],
  );

  const deleteMessage = useCallback(
    (messageId: string) => ws.send({ type: 'delete_message', message_id: messageId }),
    [ws],
  );

  return {
    ...ws,
    messages,
    participants,
    roomInfo,
    sendMessage,
    sendTyping,
    deleteMessage,
  };
}
