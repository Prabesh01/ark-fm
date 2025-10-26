#!/usr/bin/env python3
import json
import time
import requests
import sys
import os
from pypresence import Presence
from pypresence.types import ActivityType
from threading import Thread
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_rpc.log'),
        logging.StreamHandler()
    ]
)

class DiscordNowPlaying:
    def __init__(self, client_id):
        self.client_id = client_id
        self.current_song = None
        self.rpc = None
        self.connected = False
        
    def connect_discord(self, retries=3):
        """Connect to Discord RPC with retries"""
        for attempt in range(retries):
            try:
                self.rpc = Presence(self.client_id)
                self.rpc.connect()
                self.connected = True
                logging.info("✅ Connected to Discord RPC")
                return True
            except Exception as e:
                logging.warning(f"⚠️ Discord connection attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
        
        logging.error("❌ All Discord connection attempts failed")
        return False
    
    def parse_song_info(self, song_title):
        """Parse song title into artist and song name"""
        if " by " in song_title:
            parts = song_title.split(" by ", 1)
            song_name = parts[0].strip()
            artist = parts[1].strip()
            
            # Remove genre tag if present
            if " [" in artist and "]" in artist:
                artist_part, program_part = artist.split(" [", 1)
                artist = artist_part.strip()
                program = program_part.rstrip("]").strip()
        else:
            song_name,program = song_title.rsplit('[',1)
            song_name = song_name.strip() if song_name.strip() else "N/A"
            program = program.strip().strip("]")
            artist = "N/A"
        return song_name, artist, program
    
    def update_status(self, song_title):
        """Update Discord status with current song"""
        if not self.connected:
            return False

        if not song_title.strip(): return True            
        if song_title == self.current_song:
            return True
        self.current_song = song_title

        try:
            song_name, artist, program = self.parse_song_info(song_title)
            self.rpc.update(
                details=f"🎵 {song_name}",
                state=f"{artist}",
                large_image='fr' if not program else program.lower().replace(' ','_').replace("'","_"),
                large_text=f"Locked in to {program}" if program else None,
                small_image="ps",
                small_text="ARK FM",
                activity_type=ActivityType.LISTENING,
                buttons=[{"label": "Listen Along", "url": "https://ark.cote.ws/"}]
            )

            logging.info(f"✅ Status updated: {song_name} by {artist}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error updating status: {e}")
            return False
    
    def clear_status(self):
        """Clear Discord status"""
        if self.connected and self.current_song:
            try:
                self.rpc.clear()
                self.current_song = None
                logging.info("✅ Status cleared")
            except Exception as e:
                logging.error(f"❌ Error clearing status: {e}")
    
    def disconnect(self):
        """Disconnect from Discord RPC"""
        if self.connected:
            try:
                self.rpc.close()
                self.connected = False
                logging.info("✅ Disconnected from Discord RPC")
            except Exception as e:
                logging.error(f"❌ Error disconnecting: {e}")

class APIListener:
    def __init__(self, api_url, discord_app):
        self.api_url = api_url
        self.discord = discord_app
        self.running = False
    
    def parse_event(self, line):
        """Parse a single event line"""
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:])  # Remove "data:" prefix
                return data.get("streamTitle")
            except json.JSONDecodeError as e:
                logging.debug(f"JSON parse error: {e}")
        return None
    
    def listen_to_stream(self):
        """Listen to the continuous API stream"""
        logging.info(f"🎧 Starting to listen to API: {self.api_url}")
        
        while self.running:
            try:
                response = requests.get(self.api_url, stream=True, timeout=30)
                logging.info("📡 Connected to API stream")
                
                for line in response.iter_lines(decode_unicode=True):
                    if not self.running:
                        break
                    
                    if line and line.startswith("data:"):
                        song_title = self.parse_event(line)
                        if song_title:
                            self.discord.update_status(song_title)
                
            except requests.exceptions.RequestException as e:
                logging.error(f"📡 API connection error: {e}")
                time.sleep(5)
            except Exception as e:
                logging.error(f"❌ Unexpected error in API listener: {e}")
                time.sleep(5)
    
    def start(self):
        """Start listening to the API"""
        self.running = True
        self.listen_to_stream()
    
    def stop(self):
        """Stop listening"""
        self.running = False

def load_config():
    """Load configuration from file"""
    default_config = {
        "discord_client_id": "927833409097719838",
        "api_url": "https://api.zeno.fm/mounts/metadata/subscribe/bfeoaqiomuquv",
        "update_interval": 5,
        "station_name": "ARK FM",
    }
    
    return default_config

def main():
    # Load configuration
    config = load_config()
    
    # Initialize apps
    discord_app = DiscordNowPlaying(config["discord_client_id"])
    api_listener = APIListener(config["api_url"], discord_app)
    
    # Connect to Discord
    if not discord_app.connect_discord():
        logging.error("❌ Could not connect to Discord. Exiting.")
        return
    
    try:
        # Start listening to API
        logging.info("🚀 Starting application...")
        api_listener.start()
        
    except KeyboardInterrupt:
        logging.info("\n👋 Received interrupt signal...")
    finally:
        # Cleanup
        logging.info("🛑 Shutting down...")
        api_listener.stop()
        discord_app.clear_status()
        discord_app.disconnect()
        logging.info("🎯 Application shutdown complete")

if __name__ == "__main__":
    main()
