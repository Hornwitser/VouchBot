import aiohttp

from discord import Member, utils
from discord.ext.commands import Bot, check


config_template = '''# Vouchbot config
token = "your.bot.token"
help = "vhelp"
role = <role-id-to-grant>
log = <channel-id-to-log-to>
admin = <admin-role-id>
'''

import os.path
if not os.path.exists("config.py"):
    import sys
    print("config.py not found. Writing template...")
    with open('config.py', 'w') as f:
        f.write(config_template)
    sys.exit()

import config

# Can't use commands.is_owner because that doesn't let me easily reuse it
async def is_bot_owner(ctx):
    return await ctx.bot.is_owner(ctx.author)

def has_role(id):
    def predicate(ctx):
        role = utils.get(ctx.author.roles, id=id)
        return role is not None

    return check(predicate)

def no_ping(msg):
    msg = msg.replace('@everyone', '@\u200beveryone')
    return msg.replace('@here', '@\u200bhere')

bot = Bot(command_prefix='!', help_attrs={'name':config.help})

async def log(msg):
    channel = utils.get(bot.get_all_channels(), id=config.log)
    await channel.send(msg)

@bot.command()
async def vouch(ctx, member: Member):
    role = utils.get(ctx.message.author.roles, id=config.role)
    if role is not None:
        if not member.bot:
            if utils.get(member.roles, id=config.role) is None:
                mb, at = member.mention, ctx.message.author.mention
                await member.add_roles(role)
                await log("{} vouched {} as member".format(at, mb))
                msg = ("{} has been vouched as member by {}.".format(mb, at))
            else:
                msg = "{} is already vouched.".format(member.mention)
        else:
            msg = "Bots cannot be vouched."
    else:
        msg = "You must be a member to vouch for someone else."

    await ctx.send(msg)

@bot.command()
@has_role(config.admin)
async def roles(ctx):
    msg = []
    for role in ctx.message.guild.roles:
        msg.append("{}: {}".format(role.name, role.id))
    await ctx.send(no_ping("\n".join(msg)))

@bot.command()
@check(is_bot_owner)
async def name(ctx, new_name: str):
    """Set the bot's name"""
    await bot.user.edit(username=new_name)
    await ctx.send(no_ping("Changed name to {}.".format(new_name)))

@bot.command()
@check(is_bot_owner)
async def avatar(ctx):
    """Set bot avatar to the image uploaded"""
    att = ctx.message.attachments
    if len(att) == 1:
        async with aiohttp.get(att[0]['proxy_url']) as resp:
            avatar = await resp.read()
            await bot.user.edit(avatar=avatar)
            await ctx.send("Avatar changed.")
    else:
        await ctx.send("You need to upload the avatar with the command.")

bot.run(config.token)
