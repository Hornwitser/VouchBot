from sys import stderr
from traceback import print_exception

from discord import (
    AllowedMentions, Client, Guild, HTTPException, Interaction, Member,
    Role, TextChannel, utils)
from discord.app_commands import (
    CheckFailure, CommandInvokeError, CommandTree, Group, command,
    check, default_permissions, guild_only)
from discord.utils import escape_mentions as no_ping

from config import write_config


def is_bot_owner(ctx: Interaction):
    return ctx.user.id == ctx.client.my_owner_id

def is_guild_owner(ctx: Interaction):
    return ctx.user.id == ctx.guild.owner_id or is_bot_owner(ctx)

def is_admin(ctx: Interaction):
    if is_guild_owner(ctx): return True
    if ctx.guild_id is None: return False

    guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
    role_id = guild_cfg.get('admin-role-id')
    if role_id is None: return False

    role = utils.get(ctx.user.roles, id=int(role_id))
    return role is not None

async def log(guild_cfg, guild, msg):
    channel_id = guild_cfg.get('log-channel-id')
    if channel_id is not None:
        channel = guild.get_channel(int(channel_id))
        if channel is not None:
            await channel.send(msg)

def config_errors(guild_cfg, guild: Guild):
    errors = []

    if not guild.me.guild_permissions.manage_roles:
        errors.append("Bot does not have permission to grant roles")

    if 'grant-role-id' in guild_cfg:
        role = utils.get(guild.roles, id=int(guild_cfg['grant-role-id']))
        if role is not None:
            if guild.me.top_role.position < role.position:
                errors.append("Grant role is above the role of the bot")
        else:
            errors.append("Configured grant role does not exist")
    else:
        errors.append("Grant role is not set")

    if 'log-channel-id' in guild_cfg:
        ch = guild.get_channel(int(guild_cfg['log-channel-id']))
        if ch is not None and not ch.permissions_for(guild.me).send_messages:
            errors.append("Bot does not have send permission to log channel")

    return [f"\N{NO ENTRY} {e}" for e in errors]

def config_warnings(guild_cfg, guild: Guild):
    warnings = []

    if 'log-channel-id' in guild_cfg:
        ch = guild.get_channel(int(guild_cfg['log-channel-id']))
        if ch is None:
            warnings.append("Configured log channel does not exist")

    if 'admin-role-id' in guild_cfg:
        role = utils.get(guild.roles, id=int(guild_cfg['admin-role-id']))
        if role is None:
            warnings.append("Configured admin role does not exist")

    return [f"\N{WARNING SIGN} {e}" for e in warnings]

def config_problems(guild_cfg, guild: Guild):
    return config_errors(guild_cfg, guild) + config_warnings(guild_cfg, guild)

async def respond_and_warn(ctx: Interaction, msg):
    guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
    problems = config_problems(guild_cfg, ctx.guild)
    if problems:
        msg = "\n".join([msg, "\n**Warning**"] + problems)

    await ctx.response.send_message(msg)

async def vouch(ctx: Interaction, member: Member):
    guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
    errors = config_errors(guild_cfg, ctx.guild)
    if errors:
        await ctx.response.send_message("\n".join(["**Error**"] + errors))
        return

    if member != ctx.user:
        role_id = guild_cfg['grant-role-id']
        role = utils.get(ctx.user.roles, id=int(role_id))
        if not member.bot:
            if role is not None:
                if utils.get(member.roles, id=int(role_id)) is None:
                    mb, at = member.mention, ctx.user.mention
                    await member.add_roles(role)
                    await log(
                        guild_cfg, ctx.guild, f"{at} vouched {mb} as member")
                    msg = (
                        f"{mb} has been vouched as member by {at}.")
                else:
                    msg = f"{member.mention} is already vouched."
            else:
                msg = "You must be a member to vouch for someone else."
        else:
            msg = "Bots cannot be vouched."
    else:
        msg = "You can't vouch for yourself!"

    await ctx.response.send_message(msg)


class ConfigCommands(Group):
    """Manage vouch config"""

    @command()
    @check(is_admin)
    async def show(self, ctx: Interaction):
        """Show current guild config"""
        guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
        def show_role(role):
            if not role: return "not set"
            role = ctx.guild.get_role(int(role))
            return role.mention if role else "role deleted"

        def show_channel(ch):
            if not ch: return "not set"
            ch = ctx.guild.get_channel(int(ch))
            return ch.mention if ch else "channel deleted"

        await ctx.response.send_message(
            "admin-role: {}\ngrant-role: {}\nlog-channel: {}".format(
                show_role(guild_cfg.get('admin-role-id')),
                show_role(guild_cfg.get('grant-role-id')),
                show_channel(guild_cfg.get('log-channel-id')),
            ),
            allowed_mentions=AllowedMentions.none())

    @command(name="check")
    @check(is_admin)
    async def check_config(self, ctx: Interaction):
        """Check for possible problems with the config and permissions"""
        guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
        problems = config_problems(guild_cfg, ctx.guild)
        if problems:
            await ctx.response.send_message(
                "\n".join(["Found the following issues"] + problems))
        else:
            await ctx.response.send_message(
                "No issues with the configuration detected")


    @command(name="set-admin-role")
    @check(is_guild_owner)
    async def set_admin_role(self, ctx: Interaction, role: Role = None):
        """Set role granting access to guild settings on the bot"""
        guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
        if role is not None:
            if not role.is_default():
                arid = str(role.id)
                guild_cfg['admin-role-id'] = arid
                msg = no_ping(f"Set admin role to {role.name}")
            else:
                msg = "Granting admin access to everyone is not allowed"
        else:
            try:
                del guild_cfg['admin-role-id']
                msg = "Removed configured admin role"
            except KeyError:
                msg = "Admin role is not set"

        await respond_and_warn(ctx, msg)
        write_config(ctx.client.my_cfg)

    @command(name="set-grant-role")
    @check(is_admin)
    async def set_grant_role(self, ctx, role: Role = None):
        """Role bot grants upon successful vouching"""
        guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
        if role is not None:
            if not role.is_default():
                grid = str(role.id)
                guild_cfg['grant-role-id'] = grid
                msg = no_ping(f"Set grant role to {role.name}")
            else:
                msg = no_ping("Granting the @eveyone role is not possible")
        else:
            try:
                del guild_cfg['grant-role-id']
                msg = "Removed configured grant role"
            except KeyError:
                msg = "Grant role is not set"

        await respond_and_warn(ctx, msg)
        write_config(ctx.client.my_cfg)

    @command(name='set-log-channel')
    @check(is_admin)
    async def set_log_channel(self, ctx, ch: TextChannel = None):
        """Channel vouches are logged to"""
        guild_cfg = ctx.client.my_cfg['guilds'][str(ctx.guild_id)]
        if ch is not None:
            guild_cfg['log-channel-id'] = str(ch.id)
            msg = f"Set log channel to {ch.mention}"

        else:
            try:
                del guild_cfg['log-channel-id']
                msg = "Removed configured log channel"
            except KeyError:
                msg = "Log channel is not set"

        await respond_and_warn(ctx, msg)
        write_config(ctx.client.my_cfg)


def add_vouch_interactions(tree: CommandTree, guild: Guild):
    @tree.context_menu(name="Vouch Member", guild=guild)
    @guild_only
    async def vouch_menu(ctx: Interaction, member: Member):
        await vouch(ctx, member)

    @tree.command(name="vouch", guild=guild)
    @guild_only
    async def vouch_command(ctx: Interaction, member: Member):
        """Vouch for a new a member you know"""
        await vouch(ctx, member)

    tree.add_command(
        ConfigCommands(name="config", guild_only=True), guild=guild)

    @tree.error
    async def on_error(ctx: Interaction, error):
        itis = lambda cls: isinstance(error, cls)
        if itis(CommandInvokeError):
            msg = "\N{COLLISION SYMBOL} Unexpected error occured"
        elif itis(CheckFailure):
            msg = "\N{NO ENTRY SIGN} Permission denied"
        else: msg = None

        if msg is not None:
            try:
                await ctx.response.send_message(msg)
            except HTTPException:
                pass

        if itis(CommandInvokeError):
            print("Exception in command {}:".format(ctx.command), file=stderr)
            print_exception(
                type(error), error, error.__traceback__, file=stderr)
