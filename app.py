import json
from flask import Flask, request, redirect, g, render_template, jsonify, session
import requests
from urllib.parse import quote
from credentials import CLIENT_ID, CLIENT_SECRET
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Room

# Authentication Steps, paramaters, and responses are defined at https://developer.spotify.com/web-api/authorization-guide/
# Visit this url to see all the steps, parameters, and expected response.


app = Flask(__name__)
app.secret_key = 'bobs'

engine = create_engine('sqlite:///new-room-directory.db', connect_args={'check_same_thread': False})
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Spotify URLS
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)

# Server-side Parameters
CLIENT_SIDE_URL = "http://collabify-xyz.herokuapp.com"
PORT = 5000
REDIRECT_URI = "http://collabify-xyz.herokuapp.com/callback/q"
SCOPE = "playlist-modify-public playlist-modify-private user-modify-playback-state user-read-playback-state user-read-currently-playing"
STATE = ""
SHOW_DIALOG_bool = True
SHOW_DIALOG_str = str(SHOW_DIALOG_bool).lower()

auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    # "state": STATE,
    # "show_dialog": SHOW_DIALOG_str,
    "client_id": CLIENT_ID
}

# Removes a room's entry in the database when a user is finished with their session
def end_room(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    session.delete(currentRoom)
    session.commit()

# Delete a song from the playlist/queue given a Spotify URI and the position in the playlist
def delete(rc, uri, pos):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    playlist_ID = currentRoom.playlistID
    delete_url = "https://api.spotify.com/v1/playlists/" + playlist_ID + "/tracks"
    delete_auth_header = {"Authorization" : "Bearer {}".format(currentRoom.accesst),
                            "Content-Type"  :  "application/json"}
    delete_response = requests.delete(delete_url, headers=delete_auth_header, json={ "tracks": [{ "uri": uri, "positions": [pos] }] })

# Skip the user's playback forwards to the next track (ff = fast forward)
def ff(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    ff_url = "https://api.spotify.com/v1/me/player/next"
    ff_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    ff_response = requests.post(ff_url, headers=ff_auth_header)

# Skip the user's playback backwards to the previous track (rw = rewind)
def rw(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    rw_url = "https://api.spotify.com/v1/me/player/previous"
    rw_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    rw_response = requests.post(rw_url, headers=rw_auth_header)

# Returns a boolean indicating if the active player is paused
def is_paused(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    is_pause_url = "https://api.spotify.com/v1/me/player"
    is_pause_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    is_pause_response = requests.get(is_pause_url, headers=is_pause_auth_header)
    is_pause_data = json.loads(is_pause_response.text)
    return not is_pause_data["is_playing"]

# Returns a JSON file containing information about the Collabify playlist
def get_playlist_data(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    get_playlist_url = "https://api.spotify.com/v1/playlists/{}".format(currentRoom.playlistID)
    get_playlist_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    get_playlist_response = requests.get(get_playlist_url, headers=get_playlist_auth_header)
    get_playlist_data = json.loads(get_playlist_response.text)
    return get_playlist_data

# Returns a JSON file containing information about the active player
def get_player_data(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    get_player_url = "https://api.spotify.com/v1/me/player"
    get_player_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    get_player_response = requests.get(get_player_url, headers=get_player_auth_header)
    get_player_data = json.loads(get_player_response.text)
    return get_player_data

# Returns the amount of tracks in the playlist
def get_length(rc):
    jsontemp = get_playlist_data(rc)
    return jsontemp["tracks"]["total"]

# Returns a Context Object indicating the current context of the active player
def get_context(rc):
    jsontemp = get_player_data(rc)
    #return jsontemp["context"]["uri"]
    return jsontemp["context"]

# Returns True if the current context is None; ie. the app has reached the end of the playlist and is playing on autoplay
def compare_context(rc):
    return get_context(rc) == None

# Starts playback at the last track of the playlist if the playlist had previously reached an end
def start_play_offset(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    play_offset_url = "https://api.spotify.com/v1/me/player/play"
    play_offset_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    play_offset_response = requests.put(play_offset_url, headers=play_offset_auth_header, json={"context_uri" : currentRoom.playlistURI, "offset" : {"position" : currentRoom.count-1}})

# Starts playback after the first song has been added to the queue
def start_play(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    shuffle_url = "https://api.spotify.com/v1/me/player/shuffle?state=false"
    shuffle_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    shuffle_response = requests.put(shuffle_url, headers=shuffle_auth_header)
    play_select_url = "https://api.spotify.com/v1/me/player/play"
    play_select_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    play_select_response = requests.put(play_select_url, headers=play_select_auth_header, json={"context_uri" : currentRoom.playlistURI})

# Starts playback when the "Play" icon is selected   
def play(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    play_url = "https://api.spotify.com/v1/me/player/play"
    play_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    play_response = requests.put(play_url, headers=play_auth_header)
    #play_data = json.loads(play_response.text)
    #return play_data

# Stops playback when the "Pause" icon is
def pause(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    pause_url = "https://api.spotify.com/v1/me/player/pause"
    pause_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    pause_response = requests.put(pause_url, headers=pause_auth_header)
    #pause_data = json.loads(pause_response.text)
    #return pause_data


# Function to display the queue (Collabify Playlist)
def display_playlist(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    display_url = "https://api.spotify.com/v1/playlists/{}/tracks".format(currentRoom.playlistID)
    display_auth_header =  {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    display_response = requests.get(display_url, headers=display_auth_header)
    display_data = json.loads(display_response.text)
    return display_data

# Function to start playback on a given device
def select_device(rc, device_id):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    currentRoom.deviceID = device_id
    session.add(currentRoom)
    session.commit()
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    device_url = "https://api.spotify.com/v1/me/player"
    device_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    device_response = requests.put(device_url, headers=device_auth_header, json={"device_ids" : [device_id], "play" : False})
    #device_data = json.loads(device_response.text)
    
# Function to retrieve a list of the user's available devices
def get_devices(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    devices_url = "https://api.spotify.com/v1/me/player/devices"
    devices_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
    devices_response = requests.get(devices_url, headers=devices_auth_header)
    devices_data = json.loads(devices_response.text)
    return devices_data

# Function to generate room code off of a portion of random UUID string
def room_code():
    id = uuid.uuid4()
    return str(id)[24:29]

# Function to add song to a playlist given the playlist's ID, the song's URI, and the authorization token
def add(rc, song_uri):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    #if song_uri != session['uri']:
    playlist_ID = currentRoom.playlistID
    add_song_header = {"Authorization" : "Bearer {}".format(currentRoom.accesst),
                            "Content-Type"  :  "application/json"}
    add_url = "https://api.spotify.com/v1/playlists/" + playlist_ID + "/tracks"
    add_response = requests.post(add_url, headers=add_song_header, json={"uris" : [song_uri]})
    add_data = json.loads(add_response.text)
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    currentRoom.count = currentRoom.count + 1
    session.add(currentRoom)
    session.commit()

# Function to search for songs given a query; NOTE: query for endpoint needs to be passed in formatted form --> convert from plain-text recieved from front-end
def search_fr(query, search_header):
    search_url = "https://api.spotify.com/v1/search?q=" + query
    search_response = requests.get(search_url, headers=search_header)
    search_data = json.loads(search_response.text)
    return search_data

def room_args(rc, display_playlist):
    search_dict = {
        "Room Code" : rc,
        "Playlist Items" : display_playlist
    }
    return search_dict

@app.route("/")
def index():
    #session['uri'] = ''
    return render_template("index.html")

@app.route("/authenticate")
def authenticate():
    # Auth Step 1: Authorization
    url_args = "&".join(["{}={}".format(key, quote(val)) for key, val in auth_query_parameters.items()])
    auth_url = "{}/?{}".format(SPOTIFY_AUTH_URL, url_args)
    return redirect(auth_url)

@app.route("/callback/q")
def callback():
    # Auth Step 4: Requests refresh and access tokens
    auth_token = request.args['code']
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    }
    post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload)

    # Auth Step 5: Tokens are Returned to Application
    response_data = json.loads(post_request.text)
    access_token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]
    token_type = response_data["token_type"]
    expires_in = response_data["expires_in"]

    # Auth Step 6: Use the access token to access Spotify API
    authorization_header = {"Authorization": "Bearer {}".format(access_token)}

    # Get profile data
    user_profile_api_endpoint = "{}/me".format(SPOTIFY_API_URL)
    profile_response = requests.get(user_profile_api_endpoint, headers=authorization_header)
    profile_data = json.loads(profile_response.text)

    # Get user playlist data
    playlist_api_endpoint = "{}/playlists".format(profile_data["href"])
    playlists_response = requests.get(playlist_api_endpoint, headers=authorization_header)
    playlist_data = json.loads(playlists_response.text)

    # Combine profile and playlist data to display
    display_arr = [profile_data] + playlist_data["items"]

    rc = room_code()
    exists = session.query(session.query(Room).filter_by(r_c=rc).exists()).scalar()
    while exists:
        rc = room_code()
        exists = session.query(session.query(Room).filter_by(r_c=rc).exists()).scalar()

    # Creating auth header for creating a playlist
    create_playlist_header={"Authorization" : "Bearer {}".format(access_token),
                            "Content-Type"  :  "application/json"}

    # Creating a playlist for the user
    create_playlist_url = "https://api.spotify.com/v1/users/" + profile_data["id"] + "/playlists"
    create_playlist_response = requests.post(create_playlist_url, headers=create_playlist_header, json={"name":"Collabify"})
    created_playlist_data = json.loads(create_playlist_response.text)

    newRoom = Room(r_c=rc, accesst=access_token, playlistID=created_playlist_data["id"], playlistURI=created_playlist_data["uri"], count=0)
    session.add(newRoom)
    session.commit()

    playback_args = {
        "Room Code" : rc,
        "Devices" : get_devices(rc)
    }
    return render_template("playback.html", pa=playback_args)

    # return render_template("room.html", ra=room_args(rc,display_playlist(rc)))

@app.route("/join")
def join():
    return render_template("join.html")

@app.route("/search/<rc>", methods=['GET', 'POST'])
def search(rc):
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    if request.method == "POST":
        search_auth_header = {"Authorization": "Bearer {}".format(currentRoom.accesst)}
        song_name = request.form["search"]
        song_query = song_name.replace(" ", "%20") + "&type=track"
        search_results = search_fr(song_query, search_auth_header)
        search_dict = {
            "Room Code" : rc,
            "Search Results" : search_results
        }
    return render_template("search_results.html",  sd = search_dict)


@app.route("/find_room", methods=['GET', 'POST'])
def find_room():
    if request.method == "POST":
        rc = request.form["rc"]
        exists = session.query(session.query(Room).filter_by(r_c=rc).exists()).scalar()
        if exists:
            return render_template("room.html", ra=room_args(rc,display_playlist(rc)))
        else:
            return render_template("not_found.html")

@app.route("/add/<rc>/<uri>")
def add_song(rc, uri):
    add(rc, uri)
    currentRoom = session.query(Room).filter(Room.r_c == rc).one()
    if(currentRoom.count == 1):
        start_play(rc)
    elif((is_paused(rc) or compare_context(rc)) and currentRoom.count == get_length(rc)): # Checks if queue has been finished and the current playback is either paused or autoplaying radio content
        start_play_offset(rc)
    print("hello")
    return render_template("room.html", ra=room_args(rc,display_playlist(rc)))

@app.route("/playback/<rc>/<id>")
def playback(rc, id):
    # set up device
    select_device(rc, id)
    return render_template("room.html", ra=room_args(rc,display_playlist(rc)))

@app.route("/play/<rc>")
def play_song(rc):
    play(rc)
    return render_template("room.html", ra=room_args(rc,display_playlist(rc)))

@app.route("/pause/<rc>")
def pause_song(rc):
    pause(rc)
    return render_template("room.html", ra=room_args(rc,display_playlist(rc)))

@app.route("/forward/<rc>")
def fast_forward(rc):
    ff(rc)
    return render_template("room.html", ra=room_args(rc,display_playlist(rc)))

@app.route("/rewind/<rc>")
def rewind(rc):
    rw(rc)
    return render_template("room.html", ra=room_args(rc,display_playlist(rc)))

if __name__ == "__main__":
    app.run(debug=False)
