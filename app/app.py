from dotenv import load_dotenv
from flask import Flask, render_template, request
from slack_sdk import WebClient
from slackeventsapi import SlackEventAdapter
import sqlite3
import json # do i need to import?
import os
import re
import requests

load_dotenv()
app = Flask(__name__)

# Load environment variables
port = os.getenv("PORT", 5000)
debug_mode = os.getenv("DEBUG_MODE", True)

db_path = os.getenv("DB_PATH")

#uptime_api_key = os.getenv("UPTIME_API_KEY")
uptime_api_url = os.getenv("UPTIME_API_URL", "https://api.uptimerobot.com/v2/getMonitors")

slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")

# Check if required environment variables are set
#if not uptime_api_key:
#    raise ValueError("API_KEY environment variable is not set.")
if not slack_bot_token:
    raise ValueError("SLACK_BOT_TOKEN environment variable is not set.")
if not slack_signing_secret:
    raise ValueError("SLACK_SIGNING_SECRET environment variable is not set.")

if not db_path:
    raise ValueError("DB_PATH environment variable is not set.")

client = WebClient(token=slack_bot_token)
slack_event_adapter = SlackEventAdapter(
    slack_signing_secret, "/slack/events", app
)

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/slack/command", methods=["POST"])
def slack_command():
    command_text = request.form.get("text")
    channel_id = request.form.get("channel_id")
    user_id = request.form.get("user_id")
    user_name = request.form.get("user_name")
    command = request.form.get("command")

    if command == "site-status":
        response = site_status(command_text, channel_id, user_id)
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=response
        )

    
    elif command == "monitor-site":
        if not command_text:
            response = "Please provide a website. It should not include the scheme (http/https).\n Example: '/status subdomain.example.com'"
        elif not command_text or not re.match(r"^(?!https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", command_text.strip()):
            response = "Please provide a valid website without the scheme (http/https) or path (including just a '/').\nExample: '/status subdomain.example.com'"
        
    
    else:
        response = "Unknown command. How tf did you get here?"
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=response
        )
        return "", 200
    

def split_text_on_pipe(input):
    if input.count('|') != 1:
        raise ValueError("Input string must contain exactly one pipe (|) character separating the URL and API key.")
    
    try:
        url, api_key = input.split('|', 1)

        url = url.strip()
        api_key = api_key.strip()

        return url, api_key
    except ValueError:
        raise ValueError("Input string must contain exactly one pipe (|) character separating the URL and API key.")


def get_status(website, uptime_api_key):
    built_url = f"https://{uptime_api_url}?api_key={uptime_api_key}&monitors={website}"

    try:
        response = requests.post(built_url)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Error fetching status: {e}"

    if data.get("stat") != "ok":
        return "Error fetching status: Invalid response from UptimeRobot API."
    if not data.get("monitors"):
        return "No monitors found for the provided website."
    if len(data["monitors"]) > 1:
        return "Too many monitors found for the provided website."
    if len(data["monitors"]) == 0:
        return "No monitors found for the provided website."
    else:
        monitor = data["monitors"][0]
        friendly_name = monitor["friendly_name"]
        url = monitor["url"]
        status = monitor["status"]
        friendly_status = {
            0: "Paused",
            1: "Not checked yet",
            2: "Up",
            8: "Seems down",
            9: "Down",
        }.get(status, "Unknown")

        response = f"Website: {friendly_name}\nStatus: {friendly_status} (Status code: {status})\nURL: {url}"

        return response




# Check the status of a site. This is mainly for testing
def site_status(command_text):
    if not command_text:
        response = "Please provide a website. It should not include the scheme (http/https).\n Example: `/status subdomain.example.com`"
        return response

    try:
        website, uptime_api_key = split_text_on_pipe(command_text)
    except ValueError:
        response = "Improperly formatted command. There should be exactly one pipe (|) separating the website and API key. Example: `\site-status subdomain.example.com | <your api key here>`"
        return response

    if not re.match(r"^(?!https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", website.strip()):
        response = "Please provide a valid website without the scheme (the http/https part) or path.\nExample website: `subdomain.example.com`"
        return response
    else:
        response = get_status(website, uptime_api_key)
        return response


# Add a site to the list of sites to monitor
def monitor_site(command_text):
    if not command_text:
        response = "Please provide a website. It should not include the scheme (http/https).\n Example: `/status subdomain.example.com`"
        return response

    try:
        website, uptime_api_key = split_text_on_pipe(command_text)
    except ValueError:
        response = "Improperly formatted command. There should be exactly one pipe (|) separating the website and API key. Example: `\site-status subdomain.example.com | <your api key here>`"
        return response

    if not re.match(r"^(?!https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", website.strip()):
        response = "Please provide a valid website without the scheme (the http/https part) or path.\nExample website: `subdomain.example.com`"
        return response
    else:
        # Add the site to the db
        

        return response

    


if __name__ == "__main__":
    app.run(debug=debug_mode, port=port)