from collections.abc import AsyncIterator  
from contextlib import asynccontextmanager

from fastapi import FastAPI 

from src.config.settings import Settings
from src.services.orchestrator import Orchestrator 

class Server():

    def __init__(self, settings: Settings, orchestrator: Orchestrator):
        self._settings = settings 
        self._orchestrator = orchestrator
        self._app = FastAPI(title=settings.SERVICE_NAME, lifespan=self._lifespan)
        self.register_routes()
       
    @asynccontextmanager
    async def _lifespan(self, app: FastAPI) -> AsyncIterator[None]: 
        await self.run()
        try:
            yield 
        finally: 
            await self.stop()

    @property 
    def app(self):
        return self._app

    def register_routes(self):
        @self._app.get("/")
        async def root():
            return {"service": self._settings.SERVICE_NAME}

    async def run(self) -> None:
        await self._orchestrator.start()

    async def pause(self) -> None:
        await self._orchestrator.pause()

    async def stop(self) -> None:
        await self._orchestrator.stop()
    
