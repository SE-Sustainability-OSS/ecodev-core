"""
Module testing db insertion
"""
from pathlib import Path

from fastapi import Depends
from fastapi import FastAPI
from fastapi import File
from fastapi import status
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlmodel import select
from sqlmodel import Session

from ecodev_core import AppUser
from ecodev_core import attempt_to_log
from ecodev_core import create_db_and_tables
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import generic_insertion
from ecodev_core import get_access_token
from ecodev_core import get_raw_df
from ecodev_core import get_session
from ecodev_core import is_admin_user
from ecodev_core import SafeTestCase
from ecodev_core import select_user
from ecodev_core import SimpleReturn
from ecodev_core import upsert_app_users
from ecodev_core.app_user import USER_INSERTOR
from ecodev_core.db_insertion import insert_file


app = FastAPI()
test_client = TestClient(app)
DATA_DIR = Path('/app/tests/unitary/data')


def _data_insertor(df, session) -> None:
    """
    insert df data into db
    """
    session.add(AppUser(**df.iloc[0].to_dict()))
    session.commit()


@app.post('/insert-data',
          status_code=status.HTTP_201_CREATED, response_model=None)
async def insert_seed_data(*, file: UploadFile = File(...),
                           user: AppUser = Depends(is_admin_user),
                           session: Session = Depends(get_session),
                           ) -> None:
    """
    Insert seed ClimateFactor, System and Sector data
    """
    df = await get_raw_df(file, read_excel_file=False)
    _data_insertor(df, session)


@app.post('/generic-insert',
          status_code=status.HTTP_201_CREATED, response_model=SimpleReturn)
async def generic_insert(*, file: UploadFile = File(...),
                         user: AppUser = Depends(is_admin_user),
                         session: Session = Depends(get_session),
                         ) -> SimpleReturn:
    """
    Insert seed ClimateFactor, System and Sector data
    """
    df = await get_raw_df(file, read_excel_file=False)
    return generic_insertion(df, session, _data_insertor)


@app.post('/user-insert',
          status_code=status.HTTP_201_CREATED, response_model=None)
async def user_insert(*, file: UploadFile = File(...),
                      user: AppUser = Depends(is_admin_user),
                      session: Session = Depends(get_session),
                      ) -> None:
    """
    Insert seed ClimateFactor, System and Sector data
    """
    await insert_file(file, USER_INSERTOR, session)


class DbInsertionTest(SafeTestCase):
    """
    Class testing insertion
    """

    def setUp(self):
        """
        setup Class testing db insertion
        """
        super().setUp()
        create_db_and_tables(AppUser)
        delete_table(AppUser)
        with Session(engine) as session:
            upsert_app_users(DATA_DIR / 'users.json', session)

    def test_db_insertion(self):
        """
        Test db insertion
        """

        with Session(engine) as session:
            self.assertTrue(len(session.exec(select(AppUser)).all()) == 3)
            admin_token = get_access_token({'token': attempt_to_log('admin', 'admin', session)})
            with open(DATA_DIR / 'new_user.csv', 'rb') as f:
                test_client.post('/insert-data', files={'file': ('filename', f)},
                                 headers={'Authorization': f'Bearer {admin_token}'})
                self.assertTrue(len(session.exec(select(AppUser)).all()) == 4)
            self.assertTrue(select_user('toto', session).user == 'toto')

    def test_generic_insertion(self):
        """
        Test generic insertion
        """

        with Session(engine) as session:
            self.assertTrue(len(session.exec(select(AppUser)).all()) == 3)
            admin_token = get_access_token({'token': attempt_to_log('admin', 'admin', session)})
            with open(DATA_DIR / 'new_user.csv', 'rb') as f:
                resp = test_client.post('/generic-insert', files={'file': ('filename', f)},
                                        headers={'Authorization': f'Bearer {admin_token}'}).json()
            self.assertTrue(resp['success'])
            self.assertTrue(len(session.exec(select(AppUser)).all()) == 4)
            self.assertTrue(select_user('toto', session).user == 'toto')

            resp = test_client.post('/generic-insert', files={'file': ('filename', 'toto')},
                                    headers={'Authorization': f'Bearer {admin_token}'}).json()
            self.assertFalse(resp['success'])

    def test_user_insertion(self):
        """
        Test user insertion
        """

        with Session(engine) as session:
            self.assertTrue(len(session.exec(select(AppUser)).all()) == 3)
            admin_token = get_access_token({'token': attempt_to_log('admin', 'admin', session)})
            with open(DATA_DIR / 'new_user.csv', 'rb') as f:
                test_client.post('/user-insert', files={'file': ('filename', f)},
                                 headers={'Authorization': f'Bearer {admin_token}'})
                self.assertTrue(len(session.exec(select(AppUser)).all()) == 4)
