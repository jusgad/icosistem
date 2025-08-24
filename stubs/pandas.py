"""
Pandas stub for testing.
"""

class DataFrame:
    """Stub for pandas DataFrame."""
    
    def __init__(self, data=None, **kwargs):
        self.data = data or {}
    
    def to_dict(self, *args, **kwargs):
        return self.data
    
    def to_json(self, *args, **kwargs):
        import json
        return json.dumps(self.data)
    
    def head(self, n=5):
        return self
    
    def tail(self, n=5):
        return self
    
    def describe(self):
        return self
    
    def groupby(self, by):
        return self
    
    def sum(self):
        return self
    
    def mean(self):
        return self
    
    def count(self):
        return 0

def read_sql(sql, con, **kwargs):
    """Stub for pandas read_sql."""
    return DataFrame()

def read_csv(filepath, **kwargs):
    """Stub for pandas read_csv."""
    return DataFrame()

# Alias
pd = None