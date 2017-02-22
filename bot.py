from discord import Member, utils
from discord.ext.commands import Bot

import config


def no_ping(msg):
    msg = msg.replace('@everyone', '@\u200beveryone')
    return msg.replace('@here', '@\u200bhere')

bot = Bot(command_prefix='!')

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
async def roles(ctx):
    msg = []
    for role in ctx.message.guild.roles:
        msg.append("{}: {}".format(role.name, role.id))
    await ctx.send(no_ping("\n".join(msg)))

bot.run(config.token)
