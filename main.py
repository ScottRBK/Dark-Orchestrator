import uvicorn

from src.config.settings import settings
from src.server import Server
from src.services.job_service import JobService
from src.services.orchestrator import Orchestrator
from src.services.process_service import ProcessService

process_service = ProcessService()
job_service = JobService()
orchestrator = Orchestrator(process_service=process_service, job_service=job_service)

server = Server(settings, orchestrator)
app = server.app

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
    )
