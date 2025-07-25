from sqlalchemy import Column, Integer, String, BigInteger, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

user_mailbox = Table(
    'user_mailbox', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('mailbox_id', Integer, ForeignKey('mailboxes.id', ondelete="CASCADE"), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    seatable_id = Column(String, unique=True, index=True)
    name = Column(String)
    phone = Column(String, unique=True, nullable=False)
    telegram_id = Column(BigInteger, unique=True, nullable=True)


    mailboxes = relationship("Mailbox", secondary=user_mailbox, back_populates="users")

class Mailbox(Base):
    __tablename__ = 'mailboxes'

    id = Column(Integer, primary_key=True)
    seatable_id = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    description = Column(String, nullable=True)
    last_uid = Column(String, nullable=True)

    users = relationship("User", secondary=user_mailbox, back_populates="mailboxes")