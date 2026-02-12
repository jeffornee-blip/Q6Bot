import asyncio
import bot

def force_update_all_rating_roles():
    async def update_all():
        for qc in bot.queue_channels.values():
            members = await qc.rating.get_players()
            # get_players returns dicts, need to get Member objects
            guild = qc.guild
            member_objs = [guild.get_member(p['user_id']) for p in members if guild.get_member(p['user_id'])]
            if member_objs:
                await qc.update_rating_roles(*member_objs)
            await asyncio.sleep(1)
    asyncio.create_task(update_all())
