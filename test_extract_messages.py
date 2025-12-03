"""
Tests for extract_messages.py
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from extract_messages import extract_messages, list_chats, main


@pytest.fixture
def test_db():
    """Create a temporary test database with sample data."""
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = db_file.name
    db_file.close()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the necessary tables
    cursor.execute("""
        CREATE TABLE chat (
            ROWID INTEGER PRIMARY KEY,
            chat_identifier TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            text TEXT,
            attributedBody BLOB,
            date INTEGER,
            is_from_me INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE chat_message_join (
            chat_id INTEGER,
            message_id INTEGER
        )
    """)

    # Insert test data
    cursor.execute("INSERT INTO chat (ROWID, chat_identifier) VALUES (1, '+15551234567')")
    cursor.execute("INSERT INTO chat (ROWID, chat_identifier) VALUES (2, 'test@example.com')")

    # Insert messages (date is in nanoseconds since 2001-01-01)
    # Using 0 for simplicity which equals 2001-01-01
    cursor.execute("""
        INSERT INTO message (ROWID, text, attributedBody, date, is_from_me)
        VALUES (1, 'Hello', NULL, 0, 1)
    """)
    cursor.execute("""
        INSERT INTO message (ROWID, text, attributedBody, date, is_from_me)
        VALUES (2, 'Hi there', NULL, 1000000000, 0)
    """)
    cursor.execute("""
        INSERT INTO message (ROWID, text, attributedBody, date, is_from_me)
        VALUES (3, 'How are you?', NULL, 2000000000, 1)
    """)

    # Link messages to chats
    cursor.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 1)")
    cursor.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 2)")
    cursor.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (2, 3)")

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink()


class TestExtractMessages:
    """Tests for extract_messages function."""

    def test_extract_messages_basic(self, test_db, capsys):
        """Test basic message extraction."""
        extract_messages(test_db, '+15551234567')
        captured = capsys.readouterr()

        assert 'Found 2 messages' in captured.out
        assert 'Hello' in captured.out
        assert 'Hi there' in captured.out
        assert 'Me:' in captured.out
        assert 'Them:' in captured.out

    def test_extract_messages_nonexistent_chat(self, test_db, capsys):
        """Test extracting from a chat that doesn't exist."""
        extract_messages(test_db, '+15559999999')
        captured = capsys.readouterr()

        assert 'Found 0 messages' in captured.out

    def test_extract_messages_email_identifier(self, test_db, capsys):
        """Test extracting messages using email identifier."""
        extract_messages(test_db, 'test@example.com')
        captured = capsys.readouterr()

        assert 'Found 1 message' in captured.out
        assert 'How are you?' in captured.out

    def test_extract_messages_with_debug(self, test_db, capsys):
        """Test message extraction with debug flag."""
        extract_messages(test_db, '+15551234567', debug=True)
        captured = capsys.readouterr()

        assert 'Found 2 messages' in captured.out

    def test_extract_messages_invalid_db(self, capsys):
        """Test handling of invalid database path."""
        with pytest.raises(SystemExit) as exc_info:
            extract_messages('/nonexistent/path/to/db.db', '+15551234567')

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert 'Error connecting to database' in captured.err


class TestListChats:
    """Tests for list_chats function."""

    def test_list_chats(self, test_db, capsys):
        """Test listing all chats."""
        list_chats(test_db)
        captured = capsys.readouterr()

        assert 'Available chats:' in captured.out
        assert '+15551234567' in captured.out
        assert 'test@example.com' in captured.out
        assert '(2 messages)' in captured.out
        assert '(1 message' in captured.out

    def test_list_chats_sorting(self, test_db, capsys):
        """Test that chats are sorted by message count."""
        list_chats(test_db)
        captured = capsys.readouterr()

        # +15551234567 should appear before test@example.com (2 messages vs 1)
        phone_pos = captured.out.index('+15551234567')
        email_pos = captured.out.index('test@example.com')
        assert phone_pos < email_pos

    def test_list_chats_invalid_db(self, capsys):
        """Test handling of invalid database path."""
        with pytest.raises(SystemExit) as exc_info:
            list_chats('/nonexistent/path/to/db.db')

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert 'Error connecting to database' in captured.err


class TestMain:
    """Tests for main function."""

    def test_main_no_args(self, capsys):
        """Test main with no arguments."""
        with patch('sys.argv', ['extract_messages.py']):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert 'Usage:' in captured.out

    def test_main_list_command(self, test_db):
        """Test main with list command."""
        with patch('sys.argv', ['extract_messages.py', 'list', test_db]):
            with patch('extract_messages.list_chats') as mock_list:
                main()
                mock_list.assert_called_once_with(test_db)

    def test_main_extract_command(self, test_db):
        """Test main with extract command."""
        with patch('sys.argv', ['extract_messages.py', 'extract', '+15551234567', test_db]):
            with patch('extract_messages.extract_messages') as mock_extract:
                main()
                mock_extract.assert_called_once_with(test_db, '+15551234567', False)

    def test_main_extract_with_debug(self, test_db):
        """Test main with extract command and debug flag."""
        with patch('sys.argv', ['extract_messages.py', 'extract', '+15551234567', test_db, '--debug']):
            with patch('extract_messages.extract_messages') as mock_extract:
                main()
                mock_extract.assert_called_once_with(test_db, '+15551234567', True)

    def test_main_extract_no_identifier(self, capsys):
        """Test extract command without chat identifier."""
        with patch('sys.argv', ['extract_messages.py', 'extract']):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert 'chat_identifier required' in captured.out

    def test_main_unknown_command(self, capsys):
        """Test main with unknown command."""
        with patch('sys.argv', ['extract_messages.py', 'unknown']):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert 'Unknown command: unknown' in captured.out

    def test_main_default_db_path(self):
        """Test that default db path is used when not specified."""
        with patch('sys.argv', ['extract_messages.py', 'list']):
            with patch('extract_messages.list_chats') as mock_list:
                main()
                # Should be called with the default path
                call_args = mock_list.call_args[0][0]
                assert 'Library/Messages/chat.db' in call_args


class TestAttributedBodyDecoding:
    """Tests for attributed body decoding logic."""

    def test_message_with_attributed_body(self, test_db, capsys):
        """Test handling of messages with attributed body."""
        # Add a message with a mock attributed body
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert a message with placeholder blob data
        cursor.execute("""
            INSERT INTO message (ROWID, text, attributedBody, date, is_from_me)
            VALUES (4, NULL, ?, 3000000000, 1)
        """, (b'test data',))

        cursor.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 4)")
        conn.commit()
        conn.close()

        # The function should handle decoding errors gracefully
        extract_messages(test_db, '+15551234567')
        captured = capsys.readouterr()

        # Should still complete without crashing
        assert 'Found 3 messages' in captured.out

    def test_message_filtering_non_text(self, test_db, capsys):
        """Test that non-text content (like object replacement character) is filtered."""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert a message with object replacement character
        cursor.execute("""
            INSERT INTO message (ROWID, text, attributedBody, date, is_from_me)
            VALUES (5, '￼', NULL, 4000000000, 1)
        """)

        cursor.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 5)")
        conn.commit()
        conn.close()

        extract_messages(test_db, '+15551234567')
        captured = capsys.readouterr()

        # The object replacement character should not appear in output
        assert '￼' not in captured.out or 'non-text content' in captured.out
