import asyncio
from app.database import get_engine, get_session_factory
from app.repositories.ready_cakes import get_available_ready_cakes

async def main():
    factory = get_session_factory()
    async with factory() as session:
        cakes = await get_available_ready_cakes(session)
        print("Cakes count:", len(cakes))
        for c in cakes:
            print(f"ID: {c.id}, Flavor: {c.flavor}, Available: {c.available}, Price: {c.price}, Description: {c.description}")

if __name__ == "__main__":
    asyncio.run(main())
