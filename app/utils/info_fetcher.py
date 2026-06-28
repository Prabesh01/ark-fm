import requests
import asyncio, websockets, json

def get_json(url):
    return requests.get(url).json()

def parse_title(title):
    artists,song = title.split('-')
    artist = artists.split(',')[0].split('&')[0]
    song = song.split('|')[0].split('/')[0].split('(')[0]
    if len(artist.split()) > len(song.split()):
        artist,song = song,artist
    return f"{song} by {artist}"

def get_sbs_chill():
    r=get_json("https://fos.sbs.com.au/web/audio/current-song/sbs-chill?delay=90")
    return r['songDisplayName']

def process_box(id):
    r=get_json("https://prod-api.radioapi.me/metadata/"+id)
    return f"{r['song']} by {r['artist']}"

def get_box_chill():
    return process_box('1ae42584-729c-4f36-9f8f-f0be92a95bff')

def get_box_lofi():
    return process_box('70a198a4-c4eb-4f17-82c9-db07cd0361af')

def get_hiphop():
    return process_box('cf8999a0-b919-440c-95df-bab46db6b19c')

def process_chillhop(id):
    r=get_json(f"https://stream.chillhop.com/live/{id}")[0]
    return f"{r['title']} by {r['artists']}"

def get_chillhop_study():
    return process_chillhop(12363)

def get_chillhop():
    return process_chillhop(12355)

def get_chillhop_lofi():
    return process_chillhop(12354)

def get_lofi_radio():
    r=get_json("https://ec3.yesstreaming.net:2910/api/v2/history/?limit=1&offset=0&server=10")['results'][0]
    return f"{r['title']} by {r['author']}"

def process_1fm(id):
    r=get_json("https://playhistory.1cloud.fm/play_history/"+id)['now_playing']
    return f"{r['title']} by {r['artist']}"

def get_lofi_1fm():
    return process_1fm('kidsfm')

def get_absolute_90s():
    return process_1fm('90s')

def get_rock_1fm():
    return process_1fm('crock')

def process_soma(id):
    r=get_json(f"https://somafm.com/songs/{id}.json")['songs'][0]
    return f"{r['title']} by {r['artist']}"

def get_soma_80s():
    return process_soma('u80s')

def get_soft():
    r=get_json("https://onlineradiobox.com/json/fr/abclounge/playlist/0")['playlist'][0]
    return parse_title(r['name'])

def get_club():
    return parse_title(requests.get("https://www.54house.fm/playlists/now_club.txt").text)

async def process_gplayer(id):
    async with websockets.connect("wss://metadata.musicradio.com/v2/now-playing") as ws:
        await ws.send(json.dumps({"actions":[{"type":"subscribe","service":str(id)}]}))
        data = json.loads(await ws.recv())['now_playing']
        return f"{data['title']} by {data['artist']}"

def get_radiox_rock():
    return asyncio.run(process_gplayer(346))

def process_soma(id):
    r=get_json(f"https://somafm.com/songs/{id}.json")['songs'][0]
    return f"{r['title']} by {r['artist']}"

def get_indie_folk():
    return process_soma('folkfwd')

def get_covers():
    return process_soma('covers')
