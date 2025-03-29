from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
import os

# Create a SQLAlchemy instance
db = SQLAlchemy()

class User(db.Model):
    """User model for Telegram users."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(20), unique=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)  # For FSM (Finite State Machine)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.telegram_id}>"


class Account(db.Model):
    """Account model for Gmail accounts and their API keys."""
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    gmail = Column(String(100), nullable=False)
    password = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    birth_day = Column(String(2), nullable=True)
    birth_month = Column(String(2), nullable=True)
    birth_year = Column(String(4), nullable=True)
    gender = Column(String(10), nullable=True)
    api_key = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  # pending, creating, complete, failed
    error_message = Column(Text, nullable=True)
    proxy_used = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    
    def __repr__(self):
        return f"<Account {self.gmail}>"
