import os
from pathlib import Path
from dotenv import load_dotenv

import discord
from discord.ext.commands import Bot

import requests

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'
load_dotenv(ENV_FILE)

from discord import Spotify
intents = discord.Intents.default()
intents.presences = True
intents.members = True

bot = Bot(command_prefix='/', intents=intents)
bot.remove_command('help')

@bot.event
async def on_presence_update(before, after):
    if after.bot: return

    was = False
    if before.activities:
        for activity in before.activities:
            if isinstance(activity, Spotify): was = activity

    found = False
    if after.activities:
        for activity in after.activities:
            if isinstance(activity, Spotify):
                found=activity
                break

    seek=None
    if found and was:
        if was.track_id==found.track_id:
            seek=1
            # seek=int((was.start - found.start).total_seconds()*1000)
            # requests.get(f"https://ark.cote.ws/activity_seek?&uid={after.id}&seek={seek}")

    if found and not seek:
        print(f"{found.name} is now listening to {found.title} by {found.artist}")
        r=requests.get(f"https://ark.cote.ws/activity?track={found.track_id}&uid={after.id}&user={after.global_name}&profile={after.avatar}&title={found.title}&artist={found.artist}&cover={found.album_cover_url}&start={found.start}")

    if was and not found:
        requests.get(f"https://ark.cote.ws/activity_rm?uid={after.id}")

