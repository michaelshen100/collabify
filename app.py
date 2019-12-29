import json
from flask import Flask, request, redirect, g, render_template
import requests
from urllib.parse import quote
from credentials import CLIENT_ID, CLIENT_SECRET
import uuid

# Authentication Steps, paramaters, and responses are defined at https://developer.spotify.com/web-api/authorization-guide/
# Visit this url to see all the steps, parameters, and expected response.


app = Flask(__name__)

# Spotify URLS
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)

# Server-side Parameters
CLIENT_SIDE_URL = "http://127.0.0.1"
PORT = 5000
REDIRECT_URI = "{}:{}/callback/q".format(CLIENT_SIDE_URL, PORT)
SCOPE = "playlist-modify-public playlist-modify-private"
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

room_directory = dict()

def get_devices(rc):
    devices_url = "https://api.spotify.com/v1/me/player/devices"
    devices_auth_header = {"Authorization": "Bearer {}".format(room_directory[rc]["Access Token"])}
    devices_response = requests.get(devices_url, headers=devices_auth_header)
    devices_data = json.loads(devices_response.text)

# Function to generate room code off of a portion of random UUID string
def room_code():
    id = uuid.uuid4()
    return str(id)[24:29]

# Function to add song to a playlist given the playlist's ID, the song's URI, and the authorization token
def add_song(playlist_ID, song_uri, add_song_header):
    add_url = "https://api.spotify.com/v1/playlists/" + playlist_ID + "/tracks"
    add_response = requests.post(add_url, headers=add_song_header, json={"uris" : [song_uri]})
    add_data = json.loads(add_response.text)

# Function to search for songs given a query; NOTE: query for endpoint needs to be passed in formatted form --> convert from plain-text recieved from front-end
def search_fr(query, search_header):
    search_url = "https://api.spotify.com/v1/search?q=" + query
    search_response = requests.get(search_url, headers=search_header)
    search_data = json.loads(search_response.text)
    return search_data

@app.route("/")
def index():
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
    while rc in room_directory:
        rc = room_code()

    # Creating auth header for creating a playlist
    create_playlist_header={"Authorization" : "Bearer {}".format(access_token),
                            "Content-Type"  :  "application/json"}

    # Creating a playlist for the user
    create_playlist_url = "https://api.spotify.com/v1/users/" + profile_data["id"] + "/playlists"
    create_playlist_response = requests.post(create_playlist_url, headers=create_playlist_header, json={"name":"Collabify"})
    created_playlist_data = json.loads(create_playlist_response.text)

    room_directory[rc] = {
        "Access Token" : access_token,
        "Playlist ID" : created_playlist_data["id"]
    }

    return render_template("room.html", room_code=rc)

@app.route("/join")
def join():
    return render_template("join.html")

@app.route("/search/<rc>", methods=['GET', 'POST'])
def search(rc):
    if request.method == "POST":
        search_auth_header = {"Authorization": "Bearer {}".format(room_directory[rc]["Access Token"])}
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
        if rc in room_directory:
            return render_template("room.html", room_code=rc)
        else:
            return render_template("not_found.html")


if __name__ == "__main__":
    app.run(debug=True)
