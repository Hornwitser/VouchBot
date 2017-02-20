from discord import Member, utils
from discord.ext.commands import Bot

import config


def no_ping(msg):
    msg = msg.replace('@everyone', '@\u200beveryone')
    return msg.replace('@here', '@\u200bhere')

bot = Bot(command_prefix='!')

@bot.command(pass_context=True)
async def vouch(ctx, member: Member):
    role = utils.get(ctx.message.author.roles, id=config.role)
    if role:
        await member.add_roles(role)
        await ctx.send("Field promotion {}".format(member.name))
    else:
        await ctx.send("Your authority is not recongnized")

@bot.command(pass_context=True)
async def roles(ctx):
    msg = []
    for role in ctx.message.guild.roles:
        msg.append("{}: {}".format(role.name, role.id))
    await ctx.send(no_ping("\n".join(msg)))

bot.run(config.token)
