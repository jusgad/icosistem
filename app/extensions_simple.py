"""
Simplified extensions for development without all dependencies.
"""

# Simple placeholders for Flask extensions
class SimpleDB:
    def __init__(self):
        self.session = None
    
class SimpleLoginManager:
    def __init__(self):
        pass
    def user_loader(self, callback):
        return callback
    def unauthorized_handler(self, callback):
        return callback

class SimpleCache:
    def __init__(self):
        self._cache = {}
    def get(self, key):
        return self._cache.get(key)
    def set(self, key, value, timeout=None):
        self._cache[key] = value

# Initialize simple extensions
db = SimpleDB()
login_manager = SimpleLoginManager()
cache = SimpleCache()
csrf = None
mail = None
jwt = None
socketio = None
principal = None
redis_client = None
migrate = None