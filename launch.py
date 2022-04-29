from asyncio import run
from logging import basicConfig, INFO

from discord import Client, Intents, Interaction, Permissions
from discord.app_commands import CommandTree
from discord.utils import oauth_url

from config import load_config
from bot import add_vouch_interactions


basicConfig(level=INFO)

async def main():
    client = Client(intents=Intents(guilds=True))
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
            if "not guild" and app.bot_public:
                @tree.command(guild=guild)
                async def invite(ctx: Interaction):
                    """Give an invite link for this bot"""
                    await ctx.response.send_message(
                        oauth_url(
                            app.id,
                            permissions=Permissions(manage_roles=True),
                            scopes=["bot", "applications.commands"]),
                        ephemeral=True)
            await tree.sync(guild=guild)
            init = True

    async with client:
        await client.start(client.my_cfg['bot-token'])

if __name__ == '__main__':
    run(main())
