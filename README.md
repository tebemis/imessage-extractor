# iMessage Extractor

A Python tool to extract and decode iMessage text messages from macOS's Messages `chat.db` database.

## Features

- List all available chats with message counts
- Extract messages from specific chats by phone number or email
- Decode attributedBody fields to retrieve rich text content
- Handles various message formats and encodings
- Filters out non-text content (reactions, read receipts, etc.)

## Installation

This project uses [`uv`](https://emily.space/posts/251023-uv) for dependency management. If you don't have it installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install dependencies:

```bash
uv sync
```

## Usage

### List Available Chats

To see all available chats (sorted by number of texts sent):

```bash
python extract_messages.py list [db_path]
```

Example:

```bash
python extract_messages.py list chat.db
```

### Extract Messages from a Chat

To extract messages from a specific chat:

```bash
python extract_messages.py extract <chat_identifier> [db_path]
```

Example:

```bash
python extract_messages.py extract +12012493586 chat.db
```

### Debug Mode

Add `--debug` flag to see detailed decoding information:

```bash
python extract_messages.py extract +12012493586 chat.db --debug
```

## Database Location

The default iMessage database is located at:

```
~/Library/Messages/chat.db
```

The script will automatically use this location if no path is specified.

**Important:** You may need to grant your terminal application **Full Disk Access** in System Settings > Privacy & Security to read the database. If you see an "authorization denied" error, this is likely the cause.

Alternatively, you can copy the database to your working directory:

```bash
cp ~/Library/Messages/chat.db .
python extract_messages.py list chat.db
```

## Requirements

- Python 3.8+
- bpylist2 >= 4.0.0
- macOS (for accessing the iMessage database)

## Output Format

Messages are displayed in the format:

```
[YYYY-MM-DD HH:MM:SS] Sender: Message text
```

## License

MIT
