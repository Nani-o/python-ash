#!/usr/bin/env python3

import sqlite3
import pickle
from pathlib import Path

from .object_types import CACHED_OBJECT_TYPES

class Cache(object):
    def __init__(self, aap_url):
        self.data_folder = Path.home().joinpath(".local", "share", "ash")
        self.aap_url = aap_url
        self.base64_encoded_aap_url = self.aap_url.encode('utf-8').hex()
        self.user_version = 2
        self.__init_db()

    def __init_db(self):
        self.db_file = self.data_folder.joinpath('cache.db')
        self.db_user_version = self.__execute_sql('PRAGMA user_version')[0]
        if self.db_user_version != self.user_version:
            self._drop_all_tables()
            self.__execute_sql(f'PRAGMA user_version = {self.user_version}')

        for table_name in CACHED_OBJECT_TYPES:
            self._create_table(table_name)

    def _create_table(self, table_name):
        self.__execute_sql(f'''CREATE TABLE IF NOT EXISTS "{self.base64_encoded_aap_url}_{table_name}"
                              (id integer primary key,
                               data blob)''')

    def _drop_all_tables(self):
        # List all tables in the database
        tables = self.__execute_sql("SELECT name FROM sqlite_master WHERE type='table';", fetchone=False)
        for table in tables:
            self.__execute_sql(f'DROP TABLE IF EXISTS "{table[0]}"')

    def clean_cache(self, args=None):
        table_names = list(CACHED_OBJECT_TYPES)

        if args in table_names:
            table_names = [args]
        elif args:
            return

        for table_name in table_names:
            self.__execute_sql(f'DELETE FROM "{self.base64_encoded_aap_url}_{table_name}"')

    def insert_cache(self, table_name, id, data):
        data_pickled = pickle.dumps(data)
        self.__execute_sql(f'''INSERT OR REPLACE INTO "{self.base64_encoded_aap_url}_{table_name}" (id, data) VALUES(?, ?)''', (id, data_pickled))

    def load_cache(self, table_name):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute(f'''SELECT data FROM "{self.base64_encoded_aap_url}_{table_name}"''')
        rows = c.fetchall()
        conn.close()
        return [pickle.loads(row[0]) for row in rows]

    def __execute_sql(self, query, parameters=None, fetchone=True):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        if parameters:
            c.execute(query, parameters)
        else:
            c.execute(query)
        if fetchone:
            r = c.fetchone()
        else:
            r = c.fetchall()
        if not r:
            r = c.lastrowid
        conn.commit()
        conn.close()
        return r