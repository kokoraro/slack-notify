from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from slackeventsapi import SlackEventAdapter
import schedule
import time
import threading
import sqlite3
import json # do i need to import?
import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

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
verifier = SignatureVerifier(slack_signing_secret)
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
    if debug_mode:
        print(request.form)

    # Check site status
    if command == "/site-status":
        if not command_text:
            response = "Please provide a website and api key. Usage: `/site-status subdomain.example.com | <your api key here>`"
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
            return "", 200

        response = site_status(command_text)
        if not response:
            response = "Unknown error."
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=response,
                unfurl_links=False,
                unfurl_media=False
        )
        return "", 200

    # Add a site to monitoring db
    elif command == "/monitor-site":
        if not command_text:
            response = "Please provide a website and api key. Usage: `/monitor-site subdomain.example.com | <your api key here>`"
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
            return "", 200

        result = monitor_site(command_text, user_id, channel_id)
        if isinstance(result, tuple) and len(result) == 2 and result[1] == "error":
            response = result[0]
            error = True
            if debug_mode:
                print(result)
        else:
            if result:
                response = result
                error = False
            else:
                response = "Unknown error."
                error = True

        if error:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
        else:
            client.chat_postMessage(
                channel=channel_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
        return "", 200

    # Remove a site from monitoring db
    elif command == "/remove-monitor-site":
        result = remove_monitor_site(command_text, channel_id, user_id)
        if isinstance(result, tuple) and len(result) == 2 and result[1] == "error":
            response = result[0]
            error = True
            if debug_mode:
                print(result)
        else:
            if result:
                response = result
                error = False
            else:
                response = "Unknown error."
                error = True

        if error:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
        else:
            client.chat_postMessage(
                channel=channel_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
        return "", 200

    elif command == "/check-sites-in-db":
        result = check_sites_in_db()
        if isinstance(result, tuple) and len(result) == 2 and result[1] == "error":
            response = result[0]
            error = True
            if debug_mode:
                print(result)
        else:
            if result:
                response = result
                error = False
            else:
                response = "Unknown error."
                error = True
        if error:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
        else:
            client.chat_postMessage(
                channel=channel_id,
                text=response,
                unfurl_links=False,
                unfurl_media=False
            )
        return "", 200


    
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




# Get the status of a website using UptimeRobot API
def get_status(website, uptime_api_key, mode="response"):
    built_url = f"https://{uptime_api_url}?api_key={uptime_api_key}&monitors={website}"
    if debug_mode:
        print(built_url)
    
    session = requests.Session()
    retries = Retry(
        total=3,                 # Total number of retries
        backoff_factor=1,        # Wait 1s, 2s, 4s between retries
        status_forcelist=[500, 502, 503, 504],  # Retry on these HTTP status codes
        allowed_methods=["POST"]  # Retry only POST requests
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        response = session.post(built_url)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Error fetching status: {e}"
    except ValueError as e:
        return f"Error parsing JSON response: {e}"
    except json.JSONDecodeError as e:
        return f"Error decoding JSON response: {e}"
    except requests.exceptions.Timeout as e:
        return f"Request timed out: {e}"
    except requests.exceptions.TooManyRedirects as e:
        return f"Too many redirects: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching status: {e}"
    except requests.exceptions.HTTPError as e:
        return f"HTTP error occurred: {e}"
    except requests.exceptions.ConnectionError as e:
        return f"Connection error occurred: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

    """
    try:
        response = requests.post(built_url)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Error fetching status: {e}"
    """

    if data.get("stat") != "ok":
        return "Error fetching status: Invalid response from UptimeRobot API."
    if not data.get("monitors"):
        return "No monitors found for the provided website."
    if len(data["monitors"]) < 1:
        return "No monitors found for the provided website."

    if len(data["monitors"]) == 1:
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

        if mode == "response":
            response = f"Website: {friendly_name}\nStatus: {friendly_status} (Status code: {status})\nURL: {url}"
            return response
        elif mode == "plain":
            return status
        else:
            return "Invalid mode specified. Use 'response' or 'plain'."
    else:
        monitors = data["monitors"]
        for monitor in monitors:
            if monitor["friendly_name"] == website:
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

                if mode == "response":
                    response = f"Website: {friendly_name}\nStatus: {friendly_status} (Status code: {status})\nURL: {url}"
                    return response
                elif mode == "plain":
                    return status
                else:
                    return "Invalid mode specified. Use 'response' or 'plain'."

        return "No monitors found for the provided website."




# --------------------------------------------------Command handlers-------------------------------------------------

# Check the status of a site. This is mainly for testing
def site_status(command_text):
    if not command_text:
        response = "Please provide a website. It should not include the scheme (http/https).\nExample: `/status subdomain.example.com`"
        return response

    try:
        website, uptime_api_key = split_text_on_pipe(command_text)
    except ValueError:
        response = "Improperly formatted command. There should be exactly one pipe (|) separating the website and API key. Example: `/site-status subdomain.example.com | <your api key here>`"
        return response

    if not re.match(r"^(?!https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", website.strip()):
        response = "Please provide a valid website without the scheme (the http/https part) or path.\nExample website: `subdomain.example.com`"
        return response
    else:
        response = get_status(website, uptime_api_key)
        return response


# Add a site to the list of sites to monitor
def monitor_site(command_text, user_id, channel_id):
    if not command_text:
        response = "Please provide a website. It should not include the scheme (http/https).\nExample: `/status subdomain.example.com`"
        return response, "error"

    try:
        website, uptime_api_key = split_text_on_pipe(command_text)
    except ValueError:
        response = "Improperly formatted command. There should be exactly one pipe (|) separating the website and API key. Example: `/site-status subdomain.example.com | <your api key here>`"
        return response, "error"

    if not re.match(r"^(?!https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", website.strip()):
        response = "Please provide a valid website without the scheme (the http/https part) or path.\nExample website: `subdomain.example.com`"
        return response, "error"
    else:
        # Check that the info is valid
        statuses = [0, 1, 2, 8, 9]
        status = get_status(website, uptime_api_key, mode="plain")
        if not get_status(website, uptime_api_key, mode="plain") in statuses:
            response = "There was an error when verifying your site. Please check that the website is valid and that the API key is correct."
            return response, "error"

        # Add the site to the db
        try:
            db = sqlite3.connect(db_path)
            cursor = db.cursor()

            # Check if the site already exists in the database
            cursor.execute("SELECT * FROM monitor_sites WHERE user_id=? AND channel_id=? AND website=?", (user_id, channel_id, website))
            existing_site = cursor.fetchone()
            if existing_site:
                response = f"Hey <@{user_id}>! Your site ({website}) is already being monitored in this channel. Nothing has been changed."
                return response, "error"

            cursor.execute("INSERT INTO monitor_sites (user_id, channel_id, website, api_key, last_status) VALUES (?, ?, ?, ?, ?)", (user_id, channel_id, website, uptime_api_key, status))
            db.commit()
            db.close()
        except sqlite3.Error as e:
            response = f"Error adding site to the database: {e}"
            return response, "error"
        
        response = f"Hey <@{user_id}>! Your site ({website}) has been successfully added to the db of sites to monitor. Notifications will be posted in the current channel, <#{channel_id}>."

        return response


# Remove a site from the list of sites to monitor
def remove_monitor_site(command_text, channel_id, user_id):
    if not command_text:
        response = "Please provide a website. It should not include the scheme (http/https).\nExample: `/status subdomain.example.com`"
        return response

    try:
        website, uptime_api_key = split_text_on_pipe(command_text)
    except ValueError:
        response = "Improperly formatted command. There should be exactly one pipe (|) separating the website and API key. Example: `/site-status subdomain.example.com | <your api key here>`"
        return response

    if not re.match(r"^(?!https?://)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", website.strip()):
        response = "Please provide a valid website without the scheme (the http/https part) or path.\nExample website: `subdomain.example.com`"
        return response
    else:
        # Remove the site from the db
        try:
            db = sqlite3.connect(db_path)
            cursor = db.cursor()
            cursor.execute("DELETE FROM monitor_sites WHERE user_id=? AND channel_id=? AND website=?", (user_id, channel_id, website))
            db.commit()
            db.close()
        except sqlite3.Error as e:
            response = f"Error removing site from the database: {e}"
            return response
        response = f"Site ({website}) removed from the list of sites to monitor. Notifications will no longer be posted in the current channel, <#{channel_id}>."

        return response

    
def check_sites_in_db():
    try:
        db = sqlite3.connect(db_path)
        cursor = db.cursor()
        cursor.execute("SELECT user_id, channel_id, website, api_key FROM monitor_sites")
        sites = cursor.fetchall()
        db.close()
    except sqlite3.Error as e:
        if debug_mode:
            print(f"Error fetching sites from the database: {e}")
        return "Error fetching sites from the database."
    
    if not sites:
        return "No sites found in the database."
    response = "Here is a list of sites and their current status:\n\n"

    for site in sites:
        user_id = site[0]
        channel_id = site[1]
        website = site[2]
        api_key = site[3]
        status = get_status(website, api_key, mode="response")
        response += f"{status}\nAdded by: <@{user_id}>\nNotifications in: <#{channel_id}>)\n"
        if site != sites[-1]:
            response += "----------------------------------------------\n"
    
    return response


# Every minute this function will be run to check the status of all sites in the db and send a message to the channel for any that are down
def scheduled_check():
    try:
        db = sqlite3.connect(db_path)
        cursor = db.cursor()
        cursor.execute("SELECT user_id, channel_id, website, api_key, last_status FROM monitor_sites")
        sites = cursor.fetchall()
        db.close()
    except sqlite3.Error as e:
        if debug_mode:
            print(f"Error fetching sites from the database: {e}")
        return "Error fetching sites from the database."
    
    if not sites:
        return "No sites found in the database."

    for site in sites:
        user_id = site[0]
        channel_id = site[1]
        website = site[2]
        api_key = site[3]
        last_status = int(site[4])
        status = get_status(website, api_key, mode="plain")
        
        if status == last_status:
            continue
        else:
            # Update the last status in the db
            try:
                db = sqlite3.connect(db_path)
                cursor = db.cursor()
                cursor.execute("UPDATE monitor_sites SET last_status=? WHERE user_id=? AND channel_id=? AND website=?", (status, user_id, channel_id, website))
                db.commit()
                db.close()
            except sqlite3.Error as e:
                if debug_mode:
                    print(f"Error updating site status in the database: {e}")
                return "Error updating site status in the database."

        message = ""
        if status == 0:
            message = f"{website} has been paused."
        elif status == 1:
            message = f"{website} has not been checked yet."
        elif status == 2:  # Up
            message = f"Hey <@{user_id}>! Your site ({website}) is up and running!"
        elif status == 8:
            message = f"Hey <@{user_id}>! Your site ({website}) seems to be down."
        elif status == 9:  # Down
            message = f"Hey <@{user_id}>! Your site ({website}) is down."
        if not message:
            continue
        
        client.chat_postMessage(
            channel=channel_id,
            text=message,
            unfurl_links=False,
            unfurl_media=False
        )
    if debug_mode:
        print("Scheduled check completed.")
    return

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Schedule the check every 1 minutes
schedule.every().minute.at(":00").do(scheduled_check)


if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not debug_mode:
        # This is the main thread, start the scheduler
        print("Starting scheduler...")
        threading.Thread(target=run_schedule, daemon=True).start()
        
    app.run(debug=debug_mode, port=port)
