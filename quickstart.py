import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from trello import TrelloClient

import pprint
import base64
from bs4 import BeautifulSoup
import re
import csv
import pandas as pd
import json
import logging
from datetime import date
import sys

# Start changing stuff here ------------------------------------
message_identifier = "do" # What should email subjects start with in order to be considered a todo item. In lowercase.

mdtory_list = ["mandatory", "m", "-m", "mdtry", "mdtory"] # What the second word in the subject should be in order
                                                          # to consider it a mandatory task. In lowercase. 

low_p_list = ["0", "low"] # What the thrid word should be in order to consider a task low priority. Lowercase.
med_p_list = ["1", "med", "medium"] # What the thrid word should be in order to consider a task medium priority. Lowercase.
high_p_list = ["2", "high", "priority", "important", "urgent"] # What the thrid word should be in order to consider a task high priority. Lowercase.
minus_p_list = ["-1", "watch", "idc"] # What the thrid word should be in order to consider a task optional. Lowercase.

todo_label_name = "todo" # What label todo emails should be moved to. lowercase.

# Names of trello labels
label_names = ["optional", "not important", "important", "urgent"] # In order of: Optional, Not important, Important, Urgent. In lowercase
# Names of trello lists
list_names = ["personal/optional", "required", "done"] # In order of: Personal/Optional, Required, Done. In lowercase

do_logging = True # Whether you want to do logging
debug_log = True # Whether you want debug output
log_to_console = True # Whether to log to console
# Stop here -------------------------------------------

logging.basicConfig(filename=f'logs\\log {date.today().strftime("%m-%d-%Y %H-%M-%S")}.log',
                    format='%(asctime)s - %(levelname)s: %(message)s', 
                    level=logging.DEBUG if debug_log else logging.INFO,
                    datefmt='[%m-%d-%Y %H:%M:%S]'
                    )

logger = logging.getLogger()
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s", datefmt='[%m-%d-%Y %H:%M:%S]')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

if log_to_console:
    logger.addHandler(console_handler)

logger.disabled = False
if not do_logging:
    logger.disabled = True

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
creds = None
GMAIL = None

trello_client = None
# In order, Optional, Required, Doing, Done
all_lists = None
# In order, Done, Med, Low, Optional, High
labels = None


def setup_gmail_api():
    global creds, GMAIL
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        logging.debug("Gmail token file found, credentials generated")
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        logging.debug("Gmail token file not found, generating token")
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        logging.debug("Gmail token file generated")

    GMAIL = build('gmail', 'v1', credentials=creds)
    logging.info("Gmail API setup completed")

def setup_trello_api():
    global trello_client, all_lists, labels

    file = open("trello.json")

    data = json.load(file)

    trello_client = TrelloClient(
        token = data["token"],
        api_key = data["apiKey"]
    )
    logging.debug("Trello client created from trello.json credentials")

    todo_board_id = data["boardId"]
    file.close()

    todo_board = trello_client.get_board(todo_board_id)
    logging.debug("Trello board fetched")

    # In order, Optional, Required, Doing, Done
    all_lists = todo_board.all_lists()
    logging.debug("Trello lists fetched")

    # In order, Done, Med, Low, Optional, High
    labels = todo_board.get_labels()
    logging.debug("Trello labels fetched")

    logging.info("Trello API setup completed")

def add_trello_card(message_dict):
    logging.debug(f"Adding trello card for email with id {message_dict['id']}")

    board_index = 0
    current_lables = []
    if message_dict["modifiers"]["required"]:
        board_index = 1
    logging.debug("Calculated mandatory/optional for task")

    # current_lables.append(labels[1 + message_dict["modifiers"]["priority"]])
    if message_dict["modifiers"]["priority"] == 2:
        current_lables.append(next(filter(lambda x: x.name.lower() == label_names[3], labels)))
    elif message_dict["modifiers"]["priority"] == 1:
        current_lables.append(next(filter(lambda x: x.name.lower() == label_names[2], labels)))
    elif message_dict["modifiers"]["priority"] == -1:
        current_lables.append(next(filter(lambda x: x.name.lower() == label_names[0], labels)))
    else:
        current_lables.append(next(filter(lambda x: x.name.lower() == label_names[1], labels))) # Default is not important

    logging.debug(f"Calculated label {current_lables[0].name} for current message")

    card = next(filter(lambda x: x.name.lower() == list_names[board_index], all_lists)).add_card(message_dict["message_body"], position="top", labels=current_lables)
    logging.info(f"Added trello card for email with id {message_dict['id']}")
    return card

def parse_subject(subject):
    parsed = {"required": False, "priority": 0}
    cleaned = subject.lower().strip()
    
    if not cleaned.startswith(message_identifier.strip().lower()):
        logging.warning(f"{subject} had malformed format, returning default")
        return parsed # If unknown format, return default dictionary
    
    items = cleaned.split(" ")
    if len(items) == 1:
        return parsed # If no modifiers, return default
    logging.debug(f"Calculated words for subject {subject}")

    if items[1] in mdtory_list:
        parsed["required"] = True
    
    if len(items) > 1:
        priority = items[2]
        if priority in high_p_list:
            parsed["priority"] = 2
        elif priority in med_p_list:
            parsed["priority"] = 1
        elif priority in minus_p_list:
            parsed["priority"] = -1
    
    logging.info(f"Finished parsing subject {subject}")
    return parsed

def get_todo_emails(emails, GMAIL, user_id):
    cleaned_list = []

    for msg in emails:
        temp_dict = {}
        msg_id = msg["id"]
        temp_dict["id"] = msg["id"]
        message = GMAIL.users().messages().get(userId=user_id, id=msg_id).execute()
        payload = message["payload"]
        header = payload["headers"]
        
        logging.debug(f"Parsing email with id {msg_id}")
        # pprint.pprint(payload)
        # print()
        # pprint.pprint(header)
        # print("\n")

        logging.debug(f"Parsing email headers")
        for item in header: # getting the Subject
            if item['name'] == 'Subject':
                msg_subject = item['value']
                temp_dict['subject'] = msg_subject

                logging.debug(f"Located email subject")
            else:
                pass

        logging.debug("Headers parsed, subejct found")
        
        # Skip message if it doesn't start with do
        if not temp_dict["subject"].lower().startswith(message_identifier):
            # print(f"{temp_dict['subject'].lower()} does not start with do, skipping")
            continue

        temp_dict['snippet'] = message['snippet'] # fetching message snippet
        temp_dict["modifiers"] = parse_subject(temp_dict["subject"])

        try:
            
            # Fetching message body
            mssg_parts = payload['parts'] # fetching the message parts
            part_one  = mssg_parts[0] # fetching first element of the part 
            part_body = part_one['body'] # fetching body of the message
            part_data = part_body['data'] # fetching data from the body
            clean_one = part_data.replace("-","+") # decoding from Base64 to UTF-8
            clean_one = clean_one.replace("_","/") # decoding from Base64 to UTF-8
            clean_two = base64.b64decode (bytes(clean_one, 'UTF-8')) # decoding from Base64 to UTF-8
            soup = BeautifulSoup(clean_two , "lxml" )
            msg_body = soup.body()[0].get_text(" ", strip=True)
            # msg_body = "".join(msg_body) # Make a single string
            cleanr = re.compile('<.*?>') # Regex that matches all things in angle brackets
            final_msg_body = re.sub(cleanr, '', msg_body) # Remove all things in angle brackets
            # final_msg_body is a readable form of message body
            temp_dict['message_body'] = msg_body

            # print(f"Subject: {temp_dict['subject']}")
            # print(f"Message: {temp_dict['message_body']}")
            # input()

        except Exception as e:
            logging.error("An Exception occured while parsing email body, skipping", exc_info=True)
            pass

        logging.info("Parsed email body")
            
        # print(temp_dict)
        cleaned_list.append(temp_dict)

    # pprint.pprint(cleaned_list)
    logging.info("Parsed all unread emails")
    return cleaned_list

def filter_finished_tasks(user_id):
     # Look at trello "Done" column and unread any emails that match the ID, then delete the card 
    if len(next(filter(lambda x: x.name.lower() == list_names[2], all_lists)).list_cards()) > 0:
        df = pd.read_csv("finished.csv")
        logging.debug("Loaded finished.csv into dataframe")
        logging.debug(f"Enumerating cards in list {list_names[2]}")
        for card in next(filter(lambda x: x.name.lower() == list_names[2], all_lists)).list_cards():
            card_row = df[(df == card.id).any(axis=1)]
            email_id = card_row.iloc[-1].values[-1]
            logging.debug(f"Identified email id {email_id} for card id {card.id}")

            df.drop(df[(df == card.id).any(axis=1)].index, inplace=True) # Delete finished task from dataframe
            logging.debug("Deleted row from dataframe")

            card.delete()
            logging.debug("Deleted card from list")
            
            GMAIL.users().messages().modify(userId=user_id, id=email_id,body={ 'removeLabelIds': ['UNREAD']}).execute() # mark email as read
            logging.debug("Marked email as read")

        df.to_csv("finished.csv", index=False)
        logging.debug("Wrote dataframe to finished.csv")

def main():
    setup_gmail_api()
    setup_trello_api()
    
    user_id =  'me'
    label_id_one = 'INBOX'
    label_id_two = 'UNREAD'

    # Getting all the unread messages from Inbox
    unread_msgs = GMAIL.users().messages().list(userId='me',labelIds=[label_id_one, label_id_two]).execute()
    logging.info("Fetched unread emails")

    message_list = unread_msgs["messages"]
    cleaned_list = get_todo_emails(message_list, GMAIL, user_id)
    cards = []
    
    todo_label_id = ""
    results = GMAIL.users().labels().list(userId='me').execute()
    gmail_labels = results.get('labels', [])
    for glbl in gmail_labels:
        if glbl["name"].lower() == todo_label_name:
            todo_label_id = glbl["id"]
            break
    logging.debug(f"Found label id for label {todo_label_name}")

    for msg in cleaned_list:
        cards.append(add_trello_card(msg))
        # Put a card into the todo section of my email
        GMAIL.users().messages().modify(userId=user_id, id=msg["id"],body={ 'addLabelIds': [todo_label_id], "removeLabelIds": ["INBOX"] }).execute()
        logging.debug(f"Moved email with id {msg['id']} to todo label")
    
    # Write ids to CSV file
    with open("finished.csv", "a+", newline="") as f:
        writer = csv.writer(f)
        writer.writerows([[cards[i].id, cleaned_list[i]["id"]] for i in range(len(cards))])
        f.close()    
    logging.info("Added trello card ids and email ids to finished.csv")
    
    filter_finished_tasks(user_id)

    logging.info("Finished all tasks, exiting")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.error("An Exception occured, see stack trace for more details", exc_info=True)
