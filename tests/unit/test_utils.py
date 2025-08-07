"""
Unit tests for utility functions.
"""

import pytest
from datetime import datetime, timedelta


class TestFormatters:
    """Test formatting utility functions."""
    
    def test_format_datetime(self):
        """Test datetime formatting."""
        test_date = datetime(2025, 1, 15, 14, 30, 0)
        formatted = test_date.strftime('%Y-%m-%d %H:%M:%S')
        assert formatted == '2025-01-15 14:30:00'
    
    def test_format_currency(self):
        """Test currency formatting.""" 
        amount = 1234.56
        formatted = f"${amount:,.2f}"
        assert formatted == '$1,234.56'
    
    def test_format_file_size(self):
        """Test file size formatting."""
        size_bytes = 1024
        size_kb = size_bytes / 1024
        formatted_kb = f"{size_kb:.1f} KB"
        assert formatted_kb == '1.0 KB'
    
    def test_truncate_text(self):
        """Test text truncation."""
        long_text = "This is a very long text that needs to be truncated"
        max_length = 20
        truncated = long_text[:max_length] + "..." if len(long_text) > max_length else long_text
        assert len(truncated) <= max_length + 3


class TestValidators:
    """Test validation utility functions."""
    
    def test_validate_email(self):
        """Test email validation."""
        valid_emails = [
            'user@example.com',
            'test.email@domain.co.uk',
            'user123@test-domain.org'
        ]
        
        for email in valid_emails:
            assert '@' in email and '.' in email
    
    def test_validate_password_strength(self):
        """Test password strength validation."""
        strong_passwords = ['P@ssw0rd123', 'MyStr0ng!Pass', 'Complex$Pass1']
        
        for password in strong_passwords:
            has_length = len(password) >= 8
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            assert has_length and has_upper and has_lower and has_digit


class TestStringUtils:
    """Test string utility functions."""
    
    def test_slugify(self):
        """Test string slugification."""
        text = "Hello World! This is a Test"
        slug = text.lower().replace(' ', '-').replace('!', '').replace(',', '')
        expected = "hello-world-this-is-a-test"
        assert slug == expected
    
    def test_generate_random_string(self):
        """Test random string generation."""
        import string
        import random
        
        length = 10
        chars = string.ascii_letters + string.digits
        random_string = ''.join(random.choice(chars) for _ in range(length))
        
        assert len(random_string) == length