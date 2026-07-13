import asyncio
from enum import StrEnum

from src.config.settings import Settings 

class  OrchestratorStatus(StrEnum):
    INITIALISED = "initialised"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"

class Orchestrator():
    def __init__(self, settings: Settings):
        self._status = OrchestratorStatus.INITIALISED
        self._settings = settings 

    async def start(self):
        pass 

    async def pause(self): 
        pass 

    async def stop(self):
        pass 

    async def get_status(self) -> OrchestratorStatus:
        return self._status
 
    async def _heartbeat(self):
        while self._status == OrchestratorStatus.RUNNING:
            await self._get_pending_jobs() 
            await self._dispatch_pending_jobs()
            await asyncio.sleep(self._settings.HEART_BEAT_INTERVAL)

    async def _dispatch_pending_jobs(self):
        pass 

    async def _get_pending_jobs(self):
        pass 
 
