from typing import Callable
from asyncio import wait_for, shield
from asyncio.exceptions import TimeoutError as aTimeoutError
from nextcord import Interaction, SlashOption, Member, TextChannel
import traceback
import time

from core.client import dc
from core.utils import error_embed, ok_embed, parse_duration, get_nick
from core.console import log
from core.config import cfg

import bot
from . import SlashContext, autocomplete, groups

# ---------- Guild scoping ----------
servers = getattr(cfg, "DC_SLASH_SERVERS", [])
guild_kwargs = dict(guild_ids=servers) if servers else dict()

# ---------- Helpers ----------
def _parse_duration(ctx: SlashContext, s: str):
    try:
        return parse_duration(s)
    except ValueError:
        raise bot.Exc.SyntaxError(
            ctx.qc.gt("Invalid duration format. Syntax: 3h2m1s or 03:02:01.")
        )

async def run_slash(coro: Callable, interaction: Interaction, **kwargs):
    passed_time = time.time() - (((int(interaction.id) >> 22) + 1420070400000) / 1000.0)
    if passed_time >= 3.0:
        log.error("Skipping an outdated interaction.")
        return

    if not bot.bot_ready:
        await interaction.response.send_message(
            embed=error_embed("Bot is connecting, please try again later.", title="Error")
        )
        return

    qc = bot.queue_channels.get(interaction.channel_id)
    if qc is None:
        await interaction.response.send_message(
            embed=error_embed("Not in a queue channel.", title="Error")
        )
        return

    ctx = SlashContext(qc, interaction)
    try:
        await wait_for(
            shield(run_slash_coro(ctx, coro, **kwargs)),
            timeout=max(2.5 - passed_time, 0),
        )
    except (TimeoutError, aTimeoutError):
        await interaction.response.defer()

async def run_slash_coro(ctx: SlashContext, coro: Callable, **kwargs):
    log.command(
        f"{ctx.channel.guild.name} | #{ctx.channel.name} | "
        f"{get_nick(ctx.author)}: /{coro.__name__} {kwargs}"
    )
    try:
        await coro(ctx, **kwargs)
    except bot.Exc.PubobotException as e:
        await ctx.error(str(e), title=e.__class__.__name__)
    except Exception as e:
        await ctx.error(str(e), title="RuntimeError")
        log.error(
            "\n".join(
                [
                    f"Error processing /slash command {coro.__name__}.",
                    f"QC: {ctx.channel.guild.name}>#{ctx.channel.name} ({ctx.channel.id}).",
                    f"Member: {ctx.author} ({ctx.author.id}).",
                    f"Kwargs: {kwargs}.",
                    f"Exception: {e}.",
                    traceback.format_exc(),
                ]
            )
        )

# =========================
# QUEUE (ADMIN)
# =========================

@groups.admin_queue.subcommand(
    name="create_pickup", description="Create new pickup queue."
)
async def create_pickup(
    interaction: Interaction,
    name: str = SlashOption(description="Queue name"),
    size: int = SlashOption(description="Queue size", default=8),
):
    await run_slash(bot.commands.create_pickup, interaction, name=name, size=size)

@groups.admin_queue.subcommand(name="list", description="List all queues.")
async def list_queues(interaction: Interaction):
    await run_slash(bot.commands.show_queues, interaction)

@groups.admin_queue.subcommand(name="show", description="Show queue configuration.")
async def show_queue(
    interaction: Interaction,
    queue: str = SlashOption(description="Queue name"),
):
    await run_slash(bot.commands.cfg_queue, interaction, queue=queue)

show_queue.on_autocomplete("queue")(autocomplete.queues)

@groups.admin_queue.subcommand(name="set", description="Set queue variable.")
async def set_queue(
    interaction: Interaction,
    queue: str = SlashOption(description="Queue name"),
    variable: str = SlashOption(description="Variable name"),
    value: str = SlashOption(description="Value"),
):
    await run_slash(
        bot.commands.set_queue,
        interaction,
        queue=queue,
        variable=variable,
        value=value,
    )

set_queue.on_autocomplete("queue")(autocomplete.queues)
set_queue.on_autocomplete("variable")(autocomplete.queue_variables)

@groups.admin_queue.subcommand(name="delete", description="Delete queue.")
async def delete_queue(
    interaction: Interaction,
    queue: str = SlashOption(description="Queue name"),
):
    await run_slash(bot.commands.delete_queue, interaction, queue=queue)

delete_queue.on_autocomplete("queue")(autocomplete.queues)

@groups.admin_queue.subcommand(name="start", description="Start queue.")
async def start_queue(
    interaction: Interaction,
    queue: str = SlashOption(description="Queue name"),
):
    await run_slash(bot.commands.start, interaction, queue=queue)

start_queue.on_autocomplete("queue")(autocomplete.queues)

@groups.admin_queue.subcommand(name="split", description="Split queue.")
async def split_queue(
    interaction: Interaction,
    queue: str = SlashOption(description="Queue name"),
    group_size: int = SlashOption(description="Players per match", required=False),
    sort_by_rating: bool = SlashOption(description="Sort by rating", required=False),
):
    await run_slash(
        bot.commands.split,
        interaction,
        queue=queue,
        group_size=group_size,
        sort_by_rating=sort_by_rating,
    )

split_queue.on_autocomplete("queue")(autocomplete.queues)

# =========================
# CHANNEL (ADMIN)
# =========================

@groups.admin_channel.subcommand(name="enable", description="Enable bot.")
async def enable_channel(interaction: Interaction):
    if not isinstance(interaction.channel, TextChannel):
        return await interaction.response.send_message(
            embed=error_embed("Must be used in a text channel."),
            ephemeral=True,
        )
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=error_embed("Administrator permission required."),
            ephemeral=True,
        )
    if interaction.channel_id in bot.queue_channels:
        return await interaction.response.send_message(
            embed=error_embed("Channel already enabled."),
            ephemeral=True,
        )

    bot.queue_channels[interaction.channel_id] = await bot.QueueChannel.create(
        interaction.channel
    )
    await interaction.response.send_message(embed=ok_embed("Bot enabled."))

@groups.admin_channel.subcommand(name="disable", description="Disable bot.")
async def disable_channel(interaction: Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=error_embed("Administrator permission required."),
            ephemeral=True,
        )
    qc = bot.queue_channels.pop(interaction.channel_id, None)
    if qc is None:
        return await interaction.response.send_message(
            embed=error_embed("Channel not enabled."),
            ephemeral=True,
        )

    await interaction.response.send_message(embed=ok_embed("Bot disabled."))

# =========================
# ROOT COMMANDS
# =========================

@dc.slash_command(name="add", description="Add yourself.", **guild_kwargs)
async def add(
    interaction: Interaction,
    queues: str = SlashOption(description="Queues", required=False),
):
    await run_slash(bot.commands.add, interaction, queues=queues)

add.on_autocomplete("queues")(autocomplete.queues)

@dc.slash_command(name="remove", description="Remove yourself.", **guild_kwargs)
async def remove(
    interaction: Interaction,
    queues: str = SlashOption(description="Queues", required=False),
):
    await run_slash(bot.commands.remove, interaction, queues=queues)

remove.on_autocomplete("queues")(autocomplete.queues)
