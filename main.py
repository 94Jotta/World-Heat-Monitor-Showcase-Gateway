import os
import sys
import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

# Global silence protocol for clean logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WorldHeatMonitor API Gateway [Showcase Version]",
    description="High-frequency Geopolitical OSINT Ingestion & Analytics Gateway",
    version="1.0.0"
)

app.add_middleware(GZipMiddleware, minimum_size=1024)

# Configure CORS for secure domain routing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Strict domains configured in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# REAL-TIME WEBSOCKET CONNECTION MANAGER (Zero Trust model)
# ---------------------------------------------------------
class ConnectionManager:
    """Manages active WebSocket subscriptions and handles batched real-time broadcasts."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.broadcast_buffer: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_batched(self, message: Dict[str, Any]):
        """Buffers real-time signals to prevent thread congestion during high-volume spikes."""
        async with self._lock:
            self.broadcast_buffer.append(message)

    async def flush_buffer(self):
        """Wakes up every 250ms via background loops to flush buffered real-time signals."""
        if not self.active_connections or not self.broadcast_buffer:
            return
        
        async with self._lock:
            payload = {
                "type": "BATCH_INTEL_UPDATE",
                "signals": self.broadcast_buffer,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.broadcast_buffer = []

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

# ---------------------------------------------------------
# INGESTION GATEWAY & ASYNCHRONOUS OFFLOADING
# ---------------------------------------------------------
class RawIntelligenceSignal(BaseModel):
    source_vector: str
    raw_text: str
    author_handle: str
    source_url: str
    published_at: str

@app.post("/api/v1/ingest/signal", status_code=202)
async def ingest_intelligence_signal(signal: RawIntelligenceSignal, background_tasks: BackgroundTasks):
    """
    Ingest point for raw OSINT signals (X Shadow Scraper, Telegram Receiver).
    Filters noise at triage level and offloads processing to Celery background workers.
    """
    # 1. Triage Noise Filtering
    if len(signal.raw_text) < 20 or signal.raw_text.startswith("RT @"):
        raise HTTPException(status_code=400, detail="Signal dropped: Triaged as noise.")

    # 2. Asynchronous Offloading to Celery
    # Heavy NLP extraction, geocoding, and DB persistence are processed in background
    # to maintain sub-10ms API gateway response times.
    try:
        # Showcase representation of Celery task invocation
        # In production: process_intelligence_signal.apply_async(args=[...], priority=9)
        logger.info(f"Signal from {signal.author_handle} offloaded to Celery cluster.")
    except Exception as exc:
        logger.error(f"Task offloading failure: {exc}")
        raise HTTPException(status_code=500, detail="Broker congestion: Ingestion queued in buffer.")

    # 3. Broadcast real-time pre-NLP ingestion pulse to HUD clients
    await manager.broadcast_batched({
        "type": "PRE_NLP_SIGNAL_DETECTION",
        "author": signal.author_handle,
        "vector": signal.source_vector,
        "summary": signal.raw_text[:100] + "...",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "accepted", "message": "Signal queued for cognitive analysis."}

# ---------------------------------------------------------
# REAL-TIME SUBSCRIPTION ENDPOINT
# ---------------------------------------------------------
@app.websocket("/ws/intel")
async def websocket_intel_endpoint(websocket: WebSocket):
    """WebSocket subscription uplink for tactical 3D HUD clients."""
    await manager.connect(websocket)
    try:
        while True:
            # Maintain connection alive and listen for client heartbeats
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ---------------------------------------------------------
# BACKGROUND TASK SCHEDULERS
# ---------------------------------------------------------
async def ws_batch_flusher_loop():
    """Wakes up every 250ms to flush batched real-time intelligence feeds to connected HUDs."""
    while True:
        try:
            await manager.flush_buffer()
        except Exception as e:
            logger.error(f"WS flusher error: {e}")
        await asyncio.sleep(0.25)

@app.on_event("startup")
async def startup_event():
    # Spin up WebSocket batched broadcast scheduler
    asyncio.create_task(ws_batch_flusher_loop())
    logger.info("WHM Gateway Showcase operational.")

@app.get("/")
def gateway_root():
    return {
        "status": "ONLINE",
        "service": "WorldHeatMonitor API Gateway",
        "clearance_level": "RESTRICTED",
        "engine_version": "1.0.0"
    }
