import aiohttp

from discord import Member, utils
from discord.ext.commands import Bot, check

import config


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
@has_role(config.admin)
async def name(ctx, new_name: str):
    await bot.user.edit(username=new_name)
    await ctx.send(no_ping("Changed name to {}.".format(new_name)))

@bot.command()
@has_role(config.admin)
async def avatar(ctx):
    att = ctx.message.attachments
    if len(att) == 1:
        async with aiohttp.get(att[0]['proxy_url']) as resp:
            avatar = await resp.read()
            await bot.user.edit(avatar=avatar)
            await ctx.send("Avatar changed.")
    else:
        await ctx.send("You need to upload the avatar with the command.")

bot.run(config.token)
