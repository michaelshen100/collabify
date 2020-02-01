import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

class Room(Base):
    __tablename__ = 'room'
    r_c = Column(String(5), primary_key=True, unique=True, nullable=False)
    accesst = Column(String) # access token
    playlistID = Column(String)
    playlistURI = Column(String)
    deviceID = Column(String)
    count = Column(Integer)

    def __repr__(self):
        return f"Room('{self.r_c}', '{self.a_t}', '{self.playlistID}', '{self.playlistURI}', '{self.deviceID}')"


engine = create_engine('sqlite:///new-room-directory.db')
Base.metadata.create_all(engine)

