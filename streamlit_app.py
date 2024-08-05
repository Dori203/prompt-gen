import streamlit as st
import wikipedia
import re
from bs4 import BeautifulSoup
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import datetime
import random
import base64


# Spotify API setup
try:
    client_credentials_manager = SpotifyClientCredentials(
        client_id=st.secrets["SPOTIFY_CLIENT_ID"],
        client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"]
    )
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
except Exception as e:
    st.error(f"Error setting up Spotify API: {str(e)}")
    st.stop()

def shorten_text(text):
    pattern = r'\([^()]*\)|\[[^[\]]*\]'
    return re.sub(pattern, '', text)

def get_decade(year):
    return f"{year[:3]}0's"

def get_precise_decade(year):
    if isinstance(year, str):
        year = int(year)
    
    decade = (year // 10) * 10
    year_in_decade = year % 10
    
    if year_in_decade < 3:
        period = "early"
    elif year_in_decade < 7:
        period = "mid"
    else:
        period = "late"
    
    # century = "20th" if decade < 2000 else "21st"
    
    return f"{period} {decade}s"

def scale_to_word(value, scale):
    for threshold, word in scale:
        if value <= threshold:
            return word
    return scale[-1][1]


def clean_text(text):
    # Remove redundant number values
    return re.sub(r'\s*\d+\s*', ' ', text).strip()

def pitch_class_to_key(pitch_class):
    pitch_classes = ["C", "C♯/D♭", "D", "D♯/E♭", "E", "F", "F♯/G♭", "G", "G♯/A♭", "A", "A♯/B♭", "B"]
    return pitch_classes[pitch_class]

def mode_to_string(mode):
    return "Major" if mode == 1 else "Minor"

def extract_year_from_date_string(date_string):
    # First, try to find a 4-digit year in parentheses
    match = re.search(r'\((\d{4})-', date_string)
    if match:
        return int(match.group(1))
    
    # If not found, try to find any 4-digit number
    match = re.search(r'\b(\d{4})\b', date_string)
    if match:
        return int(match.group(1))
    
    # If still not found, try to parse the date
    try:
        # This will work for formats like "5 August 1966"
        date_object = datetime.strptime(date_string, "%d %B %Y")
        return date_object.year
    except ValueError:
        # If all methods fail, return None
        return None

def extract_artist_type_from_description(description):
    """
    Extracts the likely type of the artist(s) based on pronouns and specific phrases in the description.
    """
    description_lower = description.lower()
    
    # Check for band/group keywords
    band_keywords = ['band', 'group', 'duo', 'trio', 'quartet', 'ensemble']
    for keyword in band_keywords:
        if keyword in description_lower:
            match = re.search(rf'\b(\w+\s+{keyword})\b', description_lower)
            if match:
                return match.group(1)  # Returns the full match, e.g., "rock band", "girl group"
            # else:
                # return keyword  # If no specific type is found, just return "band" or "group"

    # Count pronouns
    female_pronouns = re.findall(r'\b(she|her|hers)\b', description_lower)
    male_pronouns = re.findall(r'\b(he|him|his)\b', description_lower)
    they_pronouns = re.findall(r'\b(they|them|their)\b', description_lower)

    female_count = len(female_pronouns)
    male_count = len(male_pronouns)
    they_count = len(they_pronouns)
    
    # Determine artist type based on pronoun counts
    if they_count > female_count and they_count > male_count:
        return "group"
    # elif female_count > 0 and male_count > 0:
    #     return "duet"
    elif female_count > male_count:
        return "female vocalist"
    elif male_count > female_count:
        return "male vocalist"
    else:
        return "artist"  # Type not determined


def get_spotify_track_info(search_query):
    results = sp.search(q=search_query, type='track', limit=1)
    
    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        audio_features = sp.audio_features(track['id'])[0]
        
        # Get artist genres
        artist_info = sp.artist(track['artists'][0]['id'])
        artist_genres = artist_info['genres']
        
        return {
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'album': track['album'],
            'release_date': track['album']['release_date'],
            'popularity': track['popularity'],
            'tempo': round(audio_features['tempo']),
            'key': pitch_class_to_key(audio_features['key']),
            'mode': mode_to_string(audio_features['mode']),
            'energy': audio_features['energy'],
            'danceability': audio_features['danceability'],
            'valence': audio_features['valence'],
            'artist_genres': artist_genres
        }
    return None

def get_wikipedia_song_info(song_name, song_artist):
    try:
        search_query = song_name + " " + song_artist
        print(f"Searching Wikipedia for: {search_query}")
        search_results = wikipedia.search(search_query)
        
        if not search_results:
            print("No Wikipedia search results found.")
            return None

        print(f"Wikipedia search results: {search_results}")

        selected_page = None
        selected_index = -1
        album_indice = []
        for i, result in enumerate(search_results[:4]):
            result = result.lower()
            print(f"Checking result: {result}")
            if "album" in result:
                album_indice.append(i)
                print(f"Not a match. 'album' found in '{result}'")
            elif song_name.lower() in result and "song" in result:
                selected_index = i
                print(f"A match. 'song' found in '{result}'")
                break
        if selected_index == -1:
            for i in range(len(search_results)):
                selected_index = i
                break
        selected_page = search_results[i]
        if not selected_page:
            print("No matching Wikipedia page found.")
            return None

        page = wikipedia.page(selected_page, auto_suggest=False)
        content = page.content
        html = page.html()
        
        # Extract genre using BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        release_year_wiki = ""
        release_year_row = soup.find('th', string=re.compile("Released"))
        if release_year_row:
            release_year_data = release_year_row.find_next_sibling('td')
            if release_year_data:
                release_year_wiki = release_year_data.text
        print(f"Extracted release year: {release_year_wiki}")
        genre_row = soup.find('th', string='Genre')
        genres = []
        if genre_row:
            genre_data = genre_row.find_next_sibling('td')
            if genre_data:
                genres = [shorten_text(a.text) for a in genre_data.find_all('a') if shorten_text(a.text) != ""]
        
        print(f"Extracted genres: {genres}")

        # Extract description (first paragraph, excluding any parenthetical statements)
        description = clean_text(re.sub(r'\([^)]*\)', '', content.split('\n')[0]).strip())
        print(f"Extracted description: {description[:100]}...")  # Print first 100 characters

        # Create a single sentence describing the song's genre and style
        genre_str = " and ".join(genres) if genres else "unknown genre"
        style_sentence = f"This is a {genre_str} song. {description}"

        return {
            'release_year': extract_year_from_date_string(release_year_wiki),
            'genres': genres,
            'description': description,
            'style_sentence': style_sentence
        }
    except wikipedia.exceptions.DisambiguationError as e:
        print(f"DisambiguationError: {e.options}")
        return None
    except wikipedia.exceptions.PageError:
        print(f"PageError: No Wikipedia page found for {search_query}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None


def get_random_term(terms):
    return random.choice(terms)

def scale_to_word(value, scale):
    for threshold, terms in scale:
        if value <= threshold:
            return get_random_term(terms)
    return get_random_term(scale[-1][1])  # Return a random term from the last category if value exceeds all thresholds


def generate_prompt(spotify_info, wiki_info):
    # Combine and deduplicate genres
    all_genres = set((wiki_info['genres'] if wiki_info else spotify_info['artist_genres']))
    genres = ', '.join(all_genres)

    # Get decade
    wiki_year = 4000
    if wiki_info:
        wiki_year = wiki_info['release_year']
    release_year = min([wiki_year, int(spotify_info['release_date'][:4])])
    # release_year = spotify_info['release_date'][:4]
    decade = get_precise_decade(release_year)


    energy_scale = [
        (0.3, ["mellow", "relaxed", "calm", "gentle", "soft"]),
        (0.6, ["moderate", "balanced", "steady", "mid-tempo"]),
        (1.0, ["energetic", "lively", "upbeat", "dynamic", "vibrant"])
    ]

    danceability_scale = [
        (0.3, ["contemplative", "introspective", "atmospheric", "ambient", "meditative"]),
        (0.6, ["moderately groovy", "somewhat rhythmic", "fairly lively", "mildly bouncy"]),
        (1.0, ["groovy", "rhythmic", "foot-tapping", "body-moving", "infectious"])
    ]

    valence_scale = [
        (0.3, ["melancholic", "somber", "wistful", "brooding"]),
        (0.6, ["balanced", "calm", "composed"]),
        (1.0, ["joyful", "uplifting", "cheerful", "exuberant", "optimistic"])
    ]


    energy = scale_to_word(spotify_info['energy'], energy_scale)
    danceability = scale_to_word(spotify_info['danceability'], danceability_scale)
    mood = scale_to_word(spotify_info['valence'], valence_scale)

    # Determine if it's instrumental
    instrumental = "instrumental" if spotify_info.get('instrumentalness', 0) > 0.5 else ""

    # Extract artist type from Wikipedia description
    artist_type = "artist"  # Default value
    if wiki_info and 'description' in wiki_info:

        artist_type = extract_artist_type_from_description(wiki_info['description'])

    prompt = f"a {decade} {genres}, {instrumental} song, {artist_type}, {spotify_info['tempo']} bpm, {energy}, {mood}, {danceability}, {spotify_info['key']} {spotify_info['mode']} key"

    return prompt.strip()




# Function to add background image
def add_bg_from_local(image_file):
    with open(image_file, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url(data:image/{"png"};base64,{encoded_string});
        background-size: cover;
    }}
    </style>
    """,
    unsafe_allow_html=True
    )

# Custom CSS for purple and neon green theme
st.markdown("""
    <style>
    .stApp {
        color: black;
    }
    .stTextInput > div > div > input {
        color: black;
        background-color: rgba(128, 0, 128, 0.2);
        border-color: black;
    }
    .stButton > button {
        color: black;
        background-color: rgba(128, 0, 128, 0.5);
        border-color: black;
    }
    .stTextArea > div > div > textarea {
        color: #E0E0E0;
        background-color: rgba(128, 0, 128, 0.2);
        border-color: #8A2BE2;
    }
    </style>
    """, unsafe_allow_html=True)

# Add background image
add_bg_from_local('background.jpg')  # Replace with your image path


search_query = st.text_input("Enter the song name (and optionally the artist):")

# In the Streamlit UI section, update the prompt display:
if st.button("Generate Prompt"):
    if search_query:
        with st.spinner("Fetching information..."):
            spotify_info = get_spotify_track_info(search_query)
            # wiki_search_query = spotify_info['name'] + " " + spotify_info['artist']
            wiki_info = get_wikipedia_song_info(spotify_info['name'], spotify_info['artist'])

        if spotify_info:
            # Create two columns for Spotify info
            col1, col2 = st.columns([1, 2])
            
            # Display album cover in the first column
            with col1:
                if 'images' in spotify_info['album'] and len(spotify_info['album']['images']) > 0:
                    st.image(spotify_info['album']['images'][0]['url'])
                else:
                    st.write("No album cover available")
            
            # Display song info in the second column
            with col2:
                st.subheader("Spotify Information")
                st.write(f"**Track:** {spotify_info['name']}")
                st.write(f"**Artist:** {spotify_info['artist']}")
                st.write(f"**Album:** {spotify_info['album']['name']}")
                st.write(f"**Release Date:** {spotify_info['release_date']}")
            
            # Generate and display prompt
            prompt = generate_prompt(spotify_info, wiki_info)
            st.text_area("Prompt for Generative AI", prompt, height=100)
            
        else:
            st.error("Could not find the specified track on Spotify.")
    else:
        st.warning("Please enter a song name to search.")


# You can add a small credit or info at the bottom if needed
st.markdown("""
    <style>
    .footer {
        position: fixed;
        bottom: 0;
        right: 10px;
        color: rgba(255,255,255,0.5);
        font-size: 12px;
    }
    </style>
    <div class="footer">AI Prompt Generator</div>
    """, unsafe_allow_html=True)