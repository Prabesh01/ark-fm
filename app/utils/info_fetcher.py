import requests

def get_json(url):
    return requests.get(url).json()

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
    r=get_json("https://www.1.fm/stplaylist/"+id)['nowplaying'][0]
    return f"{r['title']} by {r['artist']}"

def get_1fm_lofi():
    return process_1fm('kidsfm')

def get_absolute_90s():
    return process_1fm('90s')

def process_soma(id):
    r=get_json(f"https://somafm.com/songs/{id}.json")['songs'][0]
    return f"{r['title']} by {r['artist']}"

def get_soma_80s():
    return process_soma('u80s')

def get_soft():
    r=get_json("https://onlineradiobox.com/json/fr/abclounge/playlist/0")['playlist'][0]
    return r['name']

def get_club():
    return requests.get("https://www.54house.fm/playlists/now_club.txt").text
