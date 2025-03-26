"""
Module testing db upsertion
"""
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlmodel import Field
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import SQLModel

from ecodev_core import create_db_and_tables
from ecodev_core import db_to_value
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import field
from ecodev_core import first_or_default
from ecodev_core import get_row_versions
from ecodev_core import get_versions
from ecodev_core import Permission
from ecodev_core import SafeTestCase
from ecodev_core import sfield
from ecodev_core import upsert_data
from ecodev_core import upsert_deletor
from ecodev_core import upsert_df_data
from ecodev_core import Version


class UpFoo(SQLModel, table=True):  # type: ignore
    """
    Test class to tes db upsertion
    """
    __tablename__ = 'up_foo'
    id: Optional[int] = Field(default=None, primary_key=True)
    bar1: str = sfield()
    bar2: bool = sfield()
    bar3: str = field()
    bar4: bool = field()
    bar5: float = field()
    bar6: int = field()
    bar7: datetime = field()
    bar8: Permission = field()
    bar9: Optional[str] = field(default=None)


class UpsertorTest(SafeTestCase):
    """
    Class testing db upsertion
    """

    def setUp(self):
        """
        Class set up
        """
        super().setUp()
        create_db_and_tables(UpFoo)
        delete_table(UpFoo)
        delete_table(Version)

    def test_upsertor(self):
        """
        testing db upsertion
        """
        foo = UpFoo(bar1='bar', bar2=True, bar3='bar', bar4=False, bar5=42.42, bar6=42,
                    bar7=datetime(2025, 3, 17),
                    bar8=Permission.ADMIN)
        ffoo = UpFoo(bar1='bar', bar2=False, bar3='bbar', bar4=False, bar5=42.42, bar6=42,
                     bar7=datetime(2025, 3, 17),
                     bar8=Permission.ADMIN)
        foo2 = UpFoo(bar1='bar', bar2=True, bar3='babar', bar4=False, bar5=42.42, bar6=42,
                     bar7=datetime(2025, 3, 17),
                     bar8=Permission.ADMIN)
        foo3 = UpFoo(bar1='bar', bar2=True, bar3='bababar!', bar4=True, bar5=42.41, bar6=41,
                     bar7=datetime(2025, 3, 18),
                     bar8=Permission.Consultant, bar9='toto')

        # First insert two foos, no version
        df_init = pd.DataFrame.from_records([foo.model_dump(), ffoo.model_dump()])

        with Session(engine) as session:
            upsert_df_data(df_init, UpFoo, session)
            foos = session.exec(select(UpFoo).order_by(UpFoo.id)).all()
            versions = get_row_versions('up_foo', foos[0].id, session)

        self.assertEqual(len(foos), 2)
        self.assertEqual(foos[0].bar3, 'bar')
        self.assertEqual(len(versions), 0)

        # now only change one field of foo (bar3 from bar to babar). 1 version
        df1 = pd.DataFrame.from_records([foo2.model_dump(), ffoo.model_dump()])

        with Session(engine) as session:
            upsert_df_data(df1, UpFoo, session)
            foos = session.exec(select(UpFoo).order_by(UpFoo.id)).all()
            versions = get_row_versions('up_foo', foos[0].id, session)

        self.assertEqual(len(foos), 2)
        self.assertEqual(foos[0].bar3, 'babar')
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].table, 'up_foo')
        self.assertEqual(versions[0].column, 'bar3')
        self.assertEqual(versions[0].value, 'bar')

        #  change all fields of foo (not sfield). 8 versions, two for bar4 column
        df2 = pd.DataFrame.from_records([foo3.model_dump(), ffoo.model_dump()])

        with Session(engine) as session:
            upsert_df_data(df2, UpFoo, session)
            foos = session.exec(select(UpFoo).order_by(UpFoo.id)).all()
            versions = get_row_versions('up_foo', foos[0].id, session)
            versions_3 = get_versions('up_foo', 'bar3', foos[0].id, session)
            b_version = first_or_default(versions, lambda x: x.column == 'bar4')
            f_version = first_or_default(versions, lambda x: x.column == 'bar5')
            i_version = first_or_default(versions, lambda x: x.column == 'bar6')
            d_version = first_or_default(versions, lambda x: x.column == 'bar7')
            e_version = first_or_default(versions, lambda x: x.column == 'bar8')
            n_version = first_or_default(versions, lambda x: x.column == 'bar9')

        self.assertEqual(len(foos), 2)
        self.assertEqual(foos[0].bar3, 'bababar!')
        self.assertEqual(len(versions), 8)
        self.assertEqual(len(versions_3), 2)
        self.assertEqual(versions_3[0].table, 'up_foo')
        self.assertEqual(versions_3[0].column, 'bar3')
        self.assertEqual(versions_3[0].value, 'babar')
        self.assertEqual(versions_3[1].table, 'up_foo')
        self.assertEqual(versions_3[1].column, 'bar3')
        self.assertEqual(versions_3[1].value, 'bar')
        self.assertEqual(db_to_value(b_version.value, bool), foo2.bar4)
        self.assertEqual(db_to_value(f_version.value, float), foo2.bar5)
        self.assertEqual(db_to_value(i_version.value, int), foo2.bar6)
        self.assertEqual(db_to_value(d_version.value, datetime), foo2.bar7)
        self.assertEqual(db_to_value(e_version.value, Permission), foo2.bar8)
        self.assertTrue(db_to_value(n_version.value, str) is foo2.bar9)

        # erase foo from db, no more version.
        with Session(engine) as session:
            upsert_deletor(foo3, session)
            foos = session.exec(select(UpFoo).order_by(UpFoo.id)).all()
            versions = get_row_versions('up_foo', foos[0].id, session)

        self.assertEqual(len(foos), 1)
        self.assertEqual(len(versions), 0)

    def test_datetime(self):
        """
        Testing DB insertion for datetime fields
        """
        foo = UpFoo(bar1='bar', bar2=True, bar3='bar', bar4=False, bar5=42.42, bar6=42,
                    bar7=datetime(2025, 3, 17),
                    bar8=Permission.ADMIN)

        with Session(engine) as session:
            upsert_data([foo], session)
            upsert_data([foo], session)
            foos = session.exec(select(UpFoo)).all()

        self.assertEqual(len(foos), 1)
        self.assertEqual(len(get_row_versions('up_foo', foos[0].id, session)), 0)

        ffoo = UpFoo(bar1='bar', bar2=True, bar3='bar', bar4=False, bar5=42.42, bar6=42,
                     bar7=datetime(2025, 3, 17, 0),
                     bar8=Permission.ADMIN)

        with Session(engine) as session:
            upsert_data([ffoo], session)
            foos = session.exec(select(UpFoo)).all()

        self.assertEqual(len(foos), 1)
        self.assertEqual(len(get_row_versions('up_foo', foos[0].id, session)), 0)

        fffoo = UpFoo(bar1='bar', bar2=True, bar3='bar', bar4=False, bar5=42.42, bar6=42,
                      bar7=datetime(2025, 3, 17, 0, 0),
                      bar8=Permission.ADMIN)

        with Session(engine) as session:
            upsert_data([fffoo], session)
            foos = session.exec(select(UpFoo)).all()

        self.assertEqual(len(foos), 1)
        self.assertEqual(len(get_row_versions('up_foo', foos[0].id, session)), 0)
