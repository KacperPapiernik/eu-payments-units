import httpx
from frontend_service.app.config import settings


class BackendClients:
    def __init__(self):
        self.target: httpx.AsyncClient = httpx.AsyncClient(
            base_url=settings.target_url, timeout=15.0
        )
        self.batch: httpx.AsyncClient = httpx.AsyncClient(
            base_url=settings.sepa_batch_url, timeout=15.0
        )
        self.instant: httpx.AsyncClient = httpx.AsyncClient(
            base_url=settings.sepa_instant_url, timeout=15.0
        )

    async def close(self):
        await self.target.aclose()
        await self.batch.aclose()
        await self.instant.aclose()


clients = BackendClients()
