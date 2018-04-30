#!/usr/bin/env python3

import sqlite3
import pickle
from pathlib import Path

class Cache(object):
    def __init__(self):
        self.data_folder = Path.home().joinpath(".local", "share", "ash")
        self.__init_db()

    def __init_db(self):
        self.db_file = self.data_folder.joinpath('cache.db')
        self._create_table('job_templates')
        self._create_table('projects')
        self._create_table('inventories')

    def _create_table(self, table_name):
        self.__execute_sql(f'''CREATE TABLE IF NOT EXISTS {table_name}
                              (id integer primary key autoincrement,
                               data blob)''')

    def clean_cache(self):
        self.__execute_sql('DELETE FROM job_templates')
        self.__execute_sql('DELETE FROM projects')
        self.__execute_sql('DELETE FROM inventories')

    def insert_cache(self, table_name, data):
        data_pickled = pickle.dumps(data)
        self.__execute_sql(f'''INSERT INTO {table_name} (data) VALUES(?)''', (data_pickled,))

    def load_cache(self, table_name):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute(f'''SELECT data FROM {table_name}''')
        rows = c.fetchall()
        conn.close()
        return [pickle.loads(row[0]) for row in rows]

    def __execute_sql(self, query, parameters=None):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        if parameters:
            c.execute(query, parameters)
        else:
            c.execute(query)
        r = c.fetchone()
        if not r:
            r = c.lastrowid
        conn.commit()
        conn.close()
        return r
