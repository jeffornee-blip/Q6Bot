import asyncio
import bot

async def force_update_all_rating_roles():
    for qc in bot.queue_channels.values():
        members = await qc.rating.get_players()
        guild = qc.guild
        member_objs = [guild.get_member(p['user_id']) for p in members if guild.get_member(p['user_id'])]
        if member_objs:
            await qc.update_rating_roles(*member_objs)
        await asyncio.sleep(1)
