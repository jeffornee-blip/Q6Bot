import asyncio
from nextcord import Interaction
from nextcord.errors import HTTPException

from core.utils import ok_embed, error_embed
from core.console import log

from bot import QueueChannel

from ..context import Context


class SlashContext(Context):
	""" Context for the slash message commands """

	def __init__(self, qc: QueueChannel, interaction: Interaction):
		self.interaction = interaction
		super().__init__(qc, interaction.channel, interaction.user)

	async def _send_with_retry(self, coro_func, *args, **kwargs):
		"""Execute a Discord send with one retry on rate limit."""
		try:
			await coro_func(*args, **kwargs)
		except HTTPException as e:
			if e.status == 429:
				retry_after = getattr(e, 'retry_after', 1.0) or 1.0
				log.info(f"Rate limited, retrying after {retry_after}s")
				await asyncio.sleep(min(retry_after, 5.0))
				await coro_func(*args, **kwargs)
			else:
				raise

	async def reply(self, *args, **kwargs):
		if not self.interaction.response.is_done():
			await self._send_with_retry(self.interaction.response.send_message, *args, **kwargs)
		else:
			await self._send_with_retry(self.interaction.followup.send, *args, **kwargs)

	async def reply_dm(self, *args, **kwargs):
		if not self.interaction.response.is_done():
			await self._send_with_retry(self.interaction.response.send_message, *args, **kwargs, ephemeral=True)
		else:
			await self.interaction.user.send(*args, **kwargs)

	async def notice(self, *args, **kwargs):
		if not self.interaction.response.is_done():
			await self._send_with_retry(self.interaction.response.send_message, *args, **kwargs)
		else:
			await self._send_with_retry(self.interaction.channel.send, *args, **kwargs)

	async def ignore(self, *args, **kwargs):
		if not self.interaction.response.is_done():
			await self._send_with_retry(self.interaction.response.send_message, *args, **kwargs, ephemeral=True)

	async def error(self, *args, **kwargs):
		if not self.interaction.response.is_done():
			await self._send_with_retry(self.interaction.response.send_message, embed=error_embed(*args, **kwargs), ephemeral=True)
		else:  # this probably should never happen
			await self._send_with_retry(self.interaction.followup.send, embed=error_embed(*args, **kwargs))

	async def success(self, *args, **kwargs):
		await self.reply(embed=ok_embed(*args, **kwargs))
