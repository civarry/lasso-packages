# My notes

Lets Lasso's chat answer from a folder of your Markdown or text notes.

- **How to use it:** in chat, type **@My notes** and your question. Or just ask: Lasso looks here by
  itself when a message fits its "What's in it" line (filled in from your notes when you choose the
  folder, and editable on its page in Settings › Packages).
- **Fast on big folders:** it keeps an index of your notes in its own folder, so after the first search it
  reads only the notes that changed. A first search on thousands of notes indexes the newest ones first
  and finishes the rest over the next few searches. Hidden folders (like `.obsidian` and `.git`) are skipped.
- **Understands how you ask** (needs Lasso 0.27): it gets your message as you typed it and the question
  before it, so it
  - fixes typos ("frozendcit" searches frozendict, and the step says so; when it isn't sure, you get a
    **Did you mean …?** link, and the guess never goes to the model);
  - handles Taglish and other languages: Filipino filler words are skipped, and a rare word like
    "adobo" is enough when the other words appear in no note;
  - follows up: "show me an example" searches the previous question's subject;
  - reads dates: "last week", "yesterday", "this month", "last 10 days" use the date in a note's file
    name, front matter or title, else the day it was edited;
  - answers "what's in my notes?" with your folders and how many notes each holds;
  - says when a message isn't about your notes, so nothing is added to the chat.
- **Finds the right part:** a rare word in your question ("kestrel", "adobo", "csv") counts for more than
  a common one ("python", "file"); a note's title, file name and folder name count more than its body;
  and the passages cover different parts of the question. Each passage is the section that answers,
  with its heading and the note's date.
- **Fills in What's in it** from your folder and note names, so Lasso knows when to look (it never
  replaces a line you wrote).
- **Works well with documentation:** drop a folder of docs (converted to Markdown, with `#` headings) next
  to your notes. Split pages over 200,000 characters: the rest of a longer file isn't read.
- **Sends:** nothing. It runs `scripts/search.py` on your Mac, in Lasso's sandbox, with no internet. It
  can read only the notes folder you choose, and write only its index. The matching passages go to your
  chat model; with a cloud model, Lasso asks you first.
- **Needs:** a notes folder, and Python 3 (`/usr/bin/python3`).
