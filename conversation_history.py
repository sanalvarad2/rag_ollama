import sqlite3

class ConversationHistory:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConversationHistory, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_name="conversations.db"):
        if not hasattr(self, '_initialized'):  # Asegura que __init__ solo se ejecute una vez
            self._initialized = True
            self.db_name = db_name
            self.conn = None
            self.cursor = None
            self.initialize_database()

    def connect(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def initialize_database(self):
        self.connect()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chatId TEXT,
                user_message TEXT,
                ai_response TEXT
            )
        """)
        self.conn.commit()
        self.disconnect()

    def add_conversation(self, chat_id, user_message, ai_response):
        self.connect()
        self.cursor.execute("""
            INSERT INTO conversations (chatId, user_message, ai_response)
            VALUES (?, ?, ?)
        """, (chat_id, user_message, ai_response))
        self.conn.commit()
        self.disconnect()

    def get_last_conversations(self, chat_id):
        self.connect()
        self.cursor.execute("""
            SELECT user_message, ai_response FROM conversations
            WHERE chatId = ?
            ORDER BY id DESC
        """, (chat_id,))
        rows = self.cursor.fetchall()
        self.disconnect()
        return rows[::-1]
    
    def get_last_10_conversations(self, chat_id):
        self.connect()
        self.cursor.execute("""
            SELECT user_message, ai_response FROM conversations
            WHERE chatId = ?
            ORDER BY id DESC
            LIMIT 10
        """, (chat_id,))
        rows = self.cursor.fetchall()
        self.disconnect()
        return rows[::-1]