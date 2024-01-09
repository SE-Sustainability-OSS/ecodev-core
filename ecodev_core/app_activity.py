"""
Module implementing a simple monitoring table
"""
import inspect
from datetime import datetime
from typing import Dict
from typing import Optional

from sqlmodel import col
from sqlmodel import Field
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import SQLModel

from ecodev_core.app_user import AppUser
from ecodev_core.authentication import get_user
from ecodev_core.db_connection import engine


"""
Simple helper to retrieve the method name in which this helper is called

NB: this is meant to stay a lambda, otherwise the name retrieved is get_method, not the caller
"""


def get_method(): return inspect.stack()[1][3]


class AppActivityBase(SQLModel):
    """
    Simple monitoring class

    Attributes are:
        - user: the name of the user that triggered the monitoring log
        - application: the application in which the user triggered the monitoring log
        - method: the method called by the user  that triggered the monitoring log
        - relevant_option: if filled, complementary information on method (num of treated lines...)
    """
    user: str = Field(index=True)
    application: str = Field(index=True)
    method: str = Field(index=True)
    relevant_option: Optional[str] = Field(index=True, default=None)


class AppActivity(AppActivityBase, table=True):  # type: ignore
    """
    The table version of the AppActivityBase monitoring class
    """
    __tablename__ = 'app_activity'
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


def dash_monitor(method: str,
                 token: Dict,
                 application: str,
                 relevant_option: Optional[str] = None):
    """
    Generic dash monitor.

     Attributes are:
        - method: the method called by the user  that triggered the monitoring log
        - token: contains the information on the user that triggered the monitoring log
        - application: the application in which the user triggered the monitoring log
        - relevant_option: if filled, complementary information on method (num of treated lines...)
    """
    with Session(engine) as session:
        user = get_user(token.get('token', {}).get('access_token'))
        add_activity_to_db(method, user, application, session, relevant_option)


def fastapi_monitor(method: str,
                    user: AppUser,
                    application: str,
                    session: Session,
                    relevant_option: Optional[str] = None):
    """
    Generic fastapi monitor.

     Attributes are:
        - method: the method called by the user  that triggered the monitoring log
        - user: the name of the user that triggered the monitoring log
        - application: the application in which the user triggered the monitoring log
        - session: db connection
        - relevant_option: if filled, complementary information on method (num of treated lines...)
    """
    add_activity_to_db(method, user, application, session, relevant_option)


def add_activity_to_db(method: str,
                       user: AppUser,
                       application: str,
                       session: Session,
                       relevant_option: Optional[str] = None):
    """
    Add a new entry in AppActivity given the passed arguments
    """
    session.add(AppActivity(user=user.user, application=application, method=method,
                            relevant_option=relevant_option))
    session.commit()


def get_recent_activities(last_date: str, session: Session):
    """
    Returns all activities that happened after last_date
    """
    return session.exec(select(AppActivity).where(col(AppActivity.created_at) > last_date)).all()
