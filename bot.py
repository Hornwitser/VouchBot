from itertools import chain
from sys import stderr
from traceback import print_exception

import aiohttp
from discord import HTTPException, TextChannel, Member, Role, utils
from discord.ext.commands import \
    Bot as BotBase, CheckFailure, CommandInvokeError, UserInputError, check, \
    command, guild_only

from config import write_config


# Can't use commands.is_owner because that doesn't let me easily reuse it
async def is_bot_owner(ctx):
    return await ctx.bot.is_owner(ctx.author)

async def is_guild_owner(ctx):
    return ctx.author.id == ctx.guild.owner.id or await is_bot_owner(ctx)

async def is_admin(ctx):
    if await is_guild_owner(ctx): return True
    if ctx.guild is None: return False

    cfg = ctx.bot.my_config
    role_id = cfg['guilds'][str(ctx.guild.id)].get('admin-role-id')
    if role_id is None: return False

    role = utils.get(ctx.author.roles, id=int(role_id))
    return role is not None

def no_ping(msg):
    msg = msg.replace('@everyone', '@\u200beveryone')
    return msg.replace('@here', '@\u200bhere')

async def log(ctx, msg):
    cfg = ctx.bot.my_config
    channel_id = cfg['guilds'][str(ctx.guild.id)].get('log-channel-id')
    if channel_id is not None:
        channel = ctx.guild.get_channel(int(channel_id))
        if channel is not None:
            await channel.send(msg)

def config_errors(ctx):
    guildcfg = ctx.bot.my_config['guilds'][str(ctx.guild.id)]
    errors = []

    if not ctx.me.guild_permissions.manage_roles:
        errors.append("Bot does not have permission to grant roles")

    if 'grant-role-id' in guildcfg:
        role = utils.get(ctx.guild.roles, id=int(guildcfg['grant-role-id']))
        if role is not None:
            if ctx.me.top_role.position < role.position:
                errors.append("Grant role is above the role of the bot")
        else:
            errors.append("Configured grant role does not exist")
    else:
        errors.append("Grant role is not set")

    if 'log-channel-id' in guildcfg:
        ch = ctx.guild.get_channel(int(guildcfg['log-channel-id']))
        if ch is not None and not ch.permissions_for(ctx.me).send_messages:
            errors.append("Bot does not have send permission to log channel")

    return ["\N{NO ENTRY} {}".format(e) for e in errors]

def config_warnings(ctx):
    guildcfg = ctx.bot.my_config['guilds'][str(ctx.guild.id)]
    warnings = []

    if not ctx.me.guild_permissions.add_reactions:
        warnings.append("Bot does not have guild wide add reaction permisson, "
                        "reactions will not work in channels without it")

    if not ctx.me.guild_permissions.read_message_history:
        warnings.append("Bot does not have guild wide read message history "
                        "permisson, this may be required for reactions")

    if 'log-channel-id' in guildcfg:
        ch = ctx.guild.get_channel(int(guildcfg['log-channel-id']))
        if ch is None:
            warnings.append("Configured log channel does not exist")

    if 'admin-role-id' in guildcfg:
        role = utils.get(ctx.guild.roles, id=int(guildcfg['admin-role-id']))
        if role is None:
            warnings.append("Configured admin role does not exist")

    return ["\N{WARNING SIGN} {}".format(e) for e in warnings]

def config_problems(ctx):
    return config_errors(ctx) + config_warnings(ctx)

async def send_and_warn(ctx, msg):
    problems = config_problems(ctx)
    if problems:
        msg = "\n".join([msg, "\n**Warning**"] + problems)

    await ctx.send(msg)


class NoReplyPermission(CheckFailure):
    pass

def prefixes(bot, msg):
    def prefix_format(prefix):
        return prefix.format(bot_id=bot.user.id)

    cfg = bot.my_config
    if msg.guild is not None:
        defaults = cfg['global']['guild-command-prefixes']
        guild = cfg['guilds'][str(msg.guild.id)].get('command-prefixes', [])
        return chain(guild, map(prefix_format, defaults))

    defaults = cfg['global']['dm-command-prefixes']
    return map(prefix_format, defaults)


class Bot(BotBase):
    async def can_reply(self, ctx):
        if not ctx.channel.permissions_for(ctx.me).send_messages:
            raise NoReplyPermission("Bot can't reply")
        return True

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.my_config = config
        self.check(self.can_reply)
        self.add_command(self.vouch)
        self.add_command(self.set_admin_role)
        self.add_command(self.set_grant_role)
        self.add_command(self.set_log_channel)
        self.add_command(self.set_bot_nick)
        self.add_command(self.set_bot_prefix)
        self.add_command(self.check_config)
        self.add_command(self.name)
        self.add_command(self.avatar)

    @command()
    @guild_only()
    async def vouch(self, ctx, member: Member):
        """Vouch for a new a member you know"""
        errors = config_errors(ctx)
        if errors:
            await ctx.send("\n".join(["**Error**"] + errors))
            return

        if member != ctx.author:
            cfg = self.my_config
            role_id = cfg['guilds'][str(ctx.guild.id)]['grant-role-id']
            role = utils.get(ctx.author.roles, id=int(role_id))
            if not member.bot:
                if role is not None:
                    if utils.get(member.roles, id=int(role_id)) is None:
                        mb, at = member.mention, ctx.message.author.mention
                        await member.add_roles(role)
                        await log(ctx, "{} vouched {} as member".format(at, mb))
                        msg = ("{} has been vouched as member by {}."
                               "".format(mb, at))
                    else:
                        msg = "{} is already vouched.".format(member.mention)
                else:
                    msg = "You must be a member to vouch for someone else."
            else:
                msg = "Bots cannot be vouched."
        else:
            msg = "You can't vouch for yourself!"

        await ctx.send(msg)


    @command(name='set-admin-role')
    @guild_only()
    @check(is_guild_owner)
    async def set_admin_role(self, ctx, role: Role = None):
        """Role granting access to guild settings on the bot"""
        cfg = self.my_config
        if role is not None:
            if not role.is_default():
                arid = str(role.id)
                cfg['guilds'][str(ctx.guild.id)]['admin-role-id'] = arid
                msg = no_ping("Set admin role to {}".format(role.name))
            else:
                msg = "Granting admin access to everyone is not allowed"
        else:
            try:
                del cfg['guilds'][str(ctx.guild.id)]['admin-role-id']
                msg = "Removed configured admin role"
            except KeyError:
                msg = "Admin role is not set"

        await send_and_warn(ctx, msg)
        write_config(self.my_config)

    @command(name='set-grant-role')
    @guild_only()
    @check(is_admin)
    async def set_grant_role(self, ctx, role: Role = None):
        """Role bot grants upon successful vouching"""
        cfg = self.my_config
        if role is not None:
            if not role.is_default():
                grid = str(role.id)
                cfg['guilds'][str(ctx.guild.id)]['grant-role-id'] = grid
                msg = no_ping("Set grant role to {}".format(role.name))
            else:
                msg = no_ping("Granting the @eveyone role is not possible")
        else:
            try:
                del cfg['guilds'][str(ctx.guild.id)]['grant-role-id']
                msg = "Removed configured grant role"
            except KeyError:
                msg = "Grant role is not set"

        await send_and_warn(ctx, msg)
        write_config(self.my_config)

    @command(name='set-log-channel')
    @guild_only()
    @check(is_admin)
    async def set_log_channel(self, ctx, ch: TextChannel = None):
        """Channel vouches are logged to"""
        cfg = self.my_config
        if ch is not None:
            cfg['guilds'][str(ctx.guild.id)]['log-channel-id'] = str(ch.id)
            msg = "Set log channel to {}".format(ch.mention)

        else:
            try:
                del cfg['guilds'][str(ctx.guild.id)]['log-channel-id']
                msg = "Removed configured log channel"
            except KeyError:
                msg = "Log channel is not set"

        await send_and_warn(ctx, msg)
        write_config(self.my_config)

    @command(name='set-bot-nick')
    @guild_only()
    @check(is_admin)
    async def set_bot_nick(self, ctx, *, nick=None):
        """Set the nickname of the bot for this guild"""
        if ctx.me.guild_permissions.change_nickname:
            await ctx.me.edit(nick=nick)
            if nick is not None:
                await ctx.send(no_ping("Changed nick to {}".format(nick)))
            else:
                await ctx.send("Reset nick")
        else:
            await ctx.send("\N{NO ENTRY} Bot does not have permission "
                           "to change nickname")

    @command(name='set-bot-prefixes')
    @guild_only()
    @check(is_admin)
    async def set_bot_prefix(self, ctx, *prefixes):
        """Set the command prefixes of the bot for this guild"""
        cfg = self.my_config
        if prefixes:
            cfg['guilds'][str(ctx.guild.id)]['command-prefixes'] = prefixes
            msg = no_ping("Set bot command prefixes to {}"
                          "".format(', '.join(prefixes)))

        else:
            try:
                del cfg['guilds'][str(ctx.guild.id)]['command-prefixes']
                msg = "Removed configured command prefixes"
            except KeyError:
                msg = "Command prefixes is not set"

        await send_and_warn(ctx, msg)
        write_config(self.my_config)

    @command(name='check-config')
    @guild_only()
    @check(is_admin)
    async def check_config(self, ctx):
        """Check for possible problems with the config and permissions"""
        problems = config_problems(ctx)
        if problems:
            await ctx.send("\n".join(["Found the following issues"] + problems))
        else:
            await ctx.send("No issues with the configuration detected")

    @command()
    @check(is_bot_owner)
    async def name(self, ctx, *, new_name: str):
        """Set the bot's name"""
        await self.user.edit(username=new_name)
        await ctx.send(no_ping("Changed name to {}.".format(new_name)))

    @command()
    @check(is_bot_owner)
    async def avatar(self, ctx):
        """Set bot avatar to the image uploaded"""
        att = ctx.message.attachments
        if len(att) == 1:
            async with aiohttp.ClientSession() as session:
                async with session.get(att[0].proxy_url) as resp:
                    avatar = await resp.read()
                    await self.user.edit(avatar=avatar)
                    await ctx.send("Avatar changed.")
        else:
            await ctx.send("You need to upload the avatar with the command.")

    async def on_command_error(self, ctx, error):
        itis = lambda cls: isinstance(error, cls)
        if itis(CommandInvokeError): reaction = "\N{COLLISION SYMBOL}"
        elif itis(NoReplyPermission): reaction = "\N{ZIPPER-MOUTH FACE}"
        elif itis(CheckFailure): reaction = "\N{NO ENTRY SIGN}"
        elif itis(UserInputError): reaction = "\N{BLACK QUESTION MARK ORNAMENT}"
        else: reaction = None

        if reaction is not None:
            try:
                await ctx.message.add_reaction(reaction)
            except HTTPException:
                if ctx.channel.permissions_for(ctx.me).send_messages:
                    try:
                        await ctx.send(reaction)
                    except HTTPException:
                        pass

        if itis(CommandInvokeError):
            print("Exception in command {}:".format(ctx.command), file=stderr)
            print_exception(
                type(error), error, error.__traceback__, file=stderr
            )
