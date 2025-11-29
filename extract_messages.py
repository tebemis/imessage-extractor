#!/usr/bin/env python3
"""
Extract and decode iMessage text messages from chat.db database.
"""

import sqlite3
import sys
from pathlib import Path
from bpylist2 import archiver


def extract_messages(db_path: str, chat_identifier: str, debug: bool = False):
    """
    Extract messages from a specific chat in the iMessage database.
    
    Args:
        db_path: Path to the chat.db file
        chat_identifier: Chat identifier (phone number or email)
    """
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.DatabaseError as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        print("Please ensure your terminal application has 'Full Disk Access' in System Settings > Privacy & Security.", file=sys.stderr)
        sys.exit(1)
    cursor = conn.cursor()
    
    # Query to get messages from a specific chat
    query = """
    SELECT 
        message.ROWID,
        message.text,
        message.attributedBody,
        datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date,
        message.is_from_me
    FROM message
    JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
    JOIN chat ON chat_message_join.chat_id = chat.ROWID
    WHERE chat.chat_identifier = ?
    ORDER BY message.date ASC
    """
    
    cursor.execute(query, (chat_identifier,))
    messages = cursor.fetchall()
    
    print(f"Found {len(messages)} messages in chat: {chat_identifier}\n")
    
    for row in messages:
        rowid, text, attributed_body, date, is_from_me = row
        sender = "Me" if is_from_me else "Them"
        
        # Try to decode attributedBody if it exists
        message_text = None
        
        # First try to extract text from attributedBody using raw string extraction
        if attributed_body and len(attributed_body) > 0:
            try:
                # Try bpylist2 first
                decoded = archiver.unarchive(attributed_body)
                
                if debug:
                    print(f"\n=== DEBUG Message {rowid} ===")
                    print(f"Type: {type(decoded)}")
                    print(f"Has string attr: {hasattr(decoded, 'string')}")
                    if hasattr(decoded, 'string'):
                        print(f"String value: {decoded.string}")
                        print(f"String type: {type(decoded.string)}")
                    if hasattr(decoded, '__dict__'):
                        print(f"Dict keys: {list(decoded.__dict__.keys())}")
                        for key, value in decoded.__dict__.items():
                            print(f"  {key}: {type(value)} = {repr(value)[:100]}")
                    print("=" * 40)
                
                # The decoded object is usually an NSAttributedString
                # Try different ways to extract the text
                if hasattr(decoded, 'string'):
                    message_text = str(decoded.string)
                elif hasattr(decoded, '__dict__'):
                    # Look for common string keys
                    for key in ['NSString', 'string', 'text']:
                        if key in decoded.__dict__ and decoded.__dict__[key]:
                            message_text = str(decoded.__dict__[key])
                            break
                    # If still nothing, look for any string value
                    if not message_text:
                        for key, value in decoded.__dict__.items():
                            if isinstance(value, str) and value.strip():
                                message_text = value
                                break
                elif isinstance(decoded, str):
                    message_text = decoded
            except Exception as e:
                # If bpylist2 fails, try to extract raw UTF-8 strings from the binary data
                try:
                    # The message text is often stored as a null-terminated or length-prefixed string
                    # Look for strings that don't look like class names or attribute keys
                    
                    # Skip metadata keywords
                    skip_keywords = [
                        'streamtyped', 'NSString', 'NSAttributedString', 'NSMutableString',
                        '__kIM', 'AttributeName', 'NSData', 'bplist', 'RelativeDay',
                        'DateTime', 'NSNumber', 'NSDate', 'NSURL', 'NSValue'
                    ]
                    
                    # Try to find the longest reasonable text string
                    candidate_texts = []
                    i = 0
                    while i < len(attributed_body) - 4:
                        # Look for printable ASCII/UTF-8 sequences
                        if 32 <= attributed_body[i] <= 126:  # Printable ASCII range
                            # Find the end of this string
                            end = i
                            while end < len(attributed_body) and ((32 <= attributed_body[end] <= 126) or attributed_body[end] in [10, 13]):
                                end += 1
                            
                            if end > i + 5:  # At least 5 characters
                                try:
                                    potential = attributed_body[i:end].decode('utf-8', errors='strict').strip()
                                    # Check if this looks like actual message text, not metadata
                                    is_metadata = any(keyword in potential for keyword in skip_keywords)
                                    # Also skip very short strings or strings that are mostly numbers
                                    if not is_metadata and len(potential) > 5 and not potential.replace(' ', '').isdigit():
                                        candidate_texts.append((len(potential), potential))
                                except:
                                    pass
                            i = end
                        else:
                            i += 1
                    
                    # Use the longest candidate as it's most likely to be the actual message
                    if candidate_texts:
                        candidate_texts.sort(reverse=True)  # Sort by length descending
                        message_text = candidate_texts[0][1]
                except Exception as e2:
                    pass
                
                if debug:
                    print(f"\n=== ERROR Message {rowid} ===")
                    print(f"Error type: {type(e).__name__}")
                    print(f"Error: {e}")
                    print(f"AttributedBody length: {len(attributed_body)}")
                    print(f"First 20 bytes: {attributed_body[:20]}")
                    if message_text:
                        print(f"Extracted text: {message_text[:100]}")
        
        # Fall back to plain text field if we still don't have text
        if not message_text and text and text.strip() and text.strip() != '￼':
            message_text = text
        
        # Print the message if we have any text
        if message_text and message_text.strip() != '￼':
            print(f"[{date}] {sender}: {message_text}")
        elif debug:
            # Only show non-text content in debug mode
            print(f"[{date}] {sender}: [non-text content]")
    
    conn.close()


def list_chats(db_path: str):
    """List all available chats in the database."""
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.DatabaseError as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        print("Please ensure your terminal application has 'Full Disk Access' in System Settings > Privacy & Security.", file=sys.stderr)
        sys.exit(1)
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT chat.chat_identifier, COUNT(message.ROWID) as message_count
    FROM chat
    JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
    JOIN message ON chat_message_join.message_id = message.ROWID
    GROUP BY chat.chat_identifier
    ORDER BY message_count DESC
    """
    
    cursor.execute(query)
    chats = cursor.fetchall()
    
    print("Available chats:\n")
    for chat_id, count in chats:
        print(f"  {chat_id} ({count} messages)")
    
    conn.close()


def main():
    """Main entry point for the script."""
    # Default path to iMessage database on macOS
    default_db_path = str(Path.home() / "Library" / "Messages" / "chat.db")
    
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} list [db_path]")
        print(f"  {sys.argv[0]} extract <chat_identifier> [db_path]")
        print(f"\nDefault db_path: {default_db_path}")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        db_path = sys.argv[2] if len(sys.argv) > 2 else str(default_db_path)
        list_chats(db_path)
    elif command == "extract":
        if len(sys.argv) < 3:
            print("Error: chat_identifier required for extract command")
            sys.exit(1)
        chat_identifier = sys.argv[2]
        db_path = sys.argv[3] if len(sys.argv) > 3 else str(default_db_path)
        debug = "--debug" in sys.argv
        extract_messages(db_path, chat_identifier, debug)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
