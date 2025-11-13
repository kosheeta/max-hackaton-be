import asyncio

from rewire import Space, DependenciesModule, LoaderModule, LifecycleModule


async def main():
    async with Space().init().use():
        import rewire_sqlmodel.ext.fastapi
        import rewire_fastapi

        await LoaderModule.get().discover().load()
        await DependenciesModule.get().add(
            rewire_sqlmodel.plugin,
            rewire_fastapi.plugin,
            rewire_sqlmodel.ext.fastapi.plugin
        ).solve()

        await LifecycleModule.get().start()


if __name__ == '__main__':
    asyncio.run(main())
