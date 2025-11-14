from prisma import Prisma
from httpx import AsyncClient, Timeout

prisma = Prisma(http={"timeout": 120.0})