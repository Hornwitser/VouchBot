from asyncio import run
from logging import basicConfig, INFO

from discord import Client, Intents
from discord.app_commands import CommandTree

from config import load_config
from bot import add_vouch_interactions


basicConfig(level=INFO)

async def main():
    client = Client(intents=Intents.default())
    client.my_cfg = load_config()
    tree = CommandTree(client)
    init = False

    @client.event
    async def on_ready():
        nonlocal init
        if not init:
            app = await client.application_info()
            client.my_owner_id = app.owner.id

            guild = None # client.get_guild(ID)
            add_vouch_interactions(tree, guild)
            await tree.sync(guild=guild)
            init = True

    async with client:
        await client.start(client.my_cfg['bot-token'])

if __name__ == '__main__':
    run(main())
