```python
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()
engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///db.sqlite'))
Session = sessionmaker(bind=engine)

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    side = Column(String)
    pair = Column(String)
    tf = Column(String)
    pnl = Column(Float)
    success = Column(Boolean)

Base.metadata.create_all(engine)
