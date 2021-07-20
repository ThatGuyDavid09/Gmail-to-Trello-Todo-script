# Gmail to Trello todo

This is a script that uses the Gmail and Trello APIs to allow you to send yourself emails that will then appear in trello.

## Installation

Clone or download the repository and register for Gmail and Trello APIs.

Create a category in Gmail named Todo. This is the default, if you wish to change them, change todo_label_name at the top of [quickstart.py](quickstart.py).

Create a trello board with at least 3 lists, named something like
Personal/optional, Required, Done.
These are the defaults, if you wish to change them, change list_names at the top of [quickstart.py](quickstart.py).

Create at least 4 trello labels named something like Optional, Not important, Important, and Urgent. 
These are the defaults, if you wish to change them, change label_names at the top of [quickstart.py](quickstart.py).

Add your credentials.json to the same directory and replace all fields in trello_template.json with your values. Remove the _template from the file name.

Remove the _template from finished_template.csv.

## Usage

In order to add an item to your todo list, email yourself an email with a subject that follows this syntax: Do [mandatory|optional] [-1|0|1|2]. The mandatory/optional signifies which list the card will be placed in, and the number signifies what label it will be given, -1 being optional and 2 being urgent. If you wish to use other words, change the appropriate lists at the top of [quickstart.py](quickstart.py).

Run [quickstart.py](quickstart.py) whenever you want to update your todo list. Consider scheduling a cron job or something similar to run the script regularly.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[MIT](https://choosealicense.com/licenses/mit/)