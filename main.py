import uvicorn

from src.config.settings import settings
from src.server import create_app

app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
    )
