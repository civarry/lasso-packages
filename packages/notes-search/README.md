# My notes

Lets Lasso's chat answer from a folder of your Markdown or text notes.

- **How to use it:** in chat, type **@My notes** and your question. Or just ask: Lasso looks here by
  itself when a message fits its "What's in it" line (filled in from your notes when you choose the
  folder, and editable on its page in Settings › Packages).
- **Fast on big folders:** it keeps an index of your notes in its own folder, so after the first search it
  reads only the notes that changed. A first search on thousands of notes indexes the newest ones first
  and finishes the rest over the next few searches. Hidden folders (like `.obsidian` and `.git`) are skipped.
- **Finds the right part:** notes are ranked by how well they match (a note's title and headings count
  more), and the passage is the section that answers, with its heading and the date the note was edited.
- **Sends:** nothing. It runs `scripts/search.py` on your Mac, in Lasso's sandbox, with no internet. It
  can read only the notes folder you choose, and write only its index. The matching passages go to your
  chat model; with a cloud model, Lasso asks you first.
- **Needs:** a notes folder, and Python 3 (`/usr/bin/python3`).
