import asyncio

import dispatcher


# Запуск процесса поллинга новых апдейтов
async def main():
    await dispatcher.run_dispatcher()


if __name__ == "__main__":
    asyncio.run(main())
