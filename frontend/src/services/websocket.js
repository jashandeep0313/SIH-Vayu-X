/**
 * WebSocket client for live dashboard updates.
 *
 * Reconnects with exponential backoff — during a cyclone the dashboard is exactly
 * what must not silently stop updating.
 *
 * Event types: cyclone.detected, cyclone.updated, prediction.issued,
 * alert.issued, alert.acknowledged, pipeline.status
 */

const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws`;

export class LiveConnection {
  constructor(url = WS_URL) {
    this.url = url;
    this.socket = null;
    this.handlers = new Map();
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 30000;
    this.shouldReconnect = true;
  }

  connect() {
    // Reset the flag a previous close() set, otherwise reconnection stays
    // disabled for the life of the page once anything closes this singleton.
    this.shouldReconnect = true;
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.reconnectDelay = 1000;
      this.emit('connection.open', {});
    };

    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.emit(message.type, message.payload);
      } catch {
        // Malformed frame — drop it rather than tearing down a live connection.
      }
    };

    this.socket.onclose = () => {
      this.emit('connection.closed', {});
      if (this.shouldReconnect) {
        setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      }
    };
  }

  on(eventType, handler) {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, new Set());
    this.handlers.get(eventType).add(handler);
    return () => this.handlers.get(eventType)?.delete(handler);
  }

  emit(eventType, payload) {
    this.handlers.get(eventType)?.forEach((handler) => handler(payload));
  }

  close() {
    this.shouldReconnect = false;
    this.socket?.close();
  }
}

export const liveConnection = new LiveConnection();
