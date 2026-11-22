# My notes

Lets Lasso's chat answer from a folder of your Markdown or text notes.

- **How to use it:** in chat, type **@My notes** and your question. Or just ask: Lasso looks here by
  itself when a message fits its "What's in it" line (filled in from your notes when you choose the
  folder, and editable on its page in Settings › Packages).
- **Fast on big folders:** it keeps an index of your notes in its own folder, so after the first search it
  reads only the notes that changed. A first search on thousands of notes indexes the newest ones first
  and finishes the rest over the next few searches. Hidden folders (like `.obsidian` and `.git`) are skipped.
- **Finds the right part:** a rare word in your question ("kestrel", "adobo", "csv") counts for more than
  a common one ("python", "file"); a note's title, file name and folder name count more than its body;
  and the passages cover different parts of the question, so "which Python version does Kestrel use,
  and can it use lazy imports?" gets your Kestrel note and the lazy imports page, not three pages about
  imports. Each passage is the section that answers, with its heading and the date the note was edited.
- **Works well with documentation:** drop a folder of docs (converted to Markdown, with `#` headings) next
  to your notes. Split pages over 200,000 characters: the rest of a longer file isn't read.
- **Sends:** nothing. It runs `scripts/search.py` on your Mac, in Lasso's sandbox, with no internet. It
  can read only the notes folder you choose, and write only its index. The matching passages go to your
  chat model; with a cloud model, Lasso asks you first.
- **Needs:** a notes folder, and Python 3 (`/usr/bin/python3`).
