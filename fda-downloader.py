import requests
import pandas as pd
import zipfile
import os
import json
import sqlite3
import argparse

def create_db_connection(db_file):
    conn = sqlite3.connect(db_file)
    return conn

def create_table_from_df(df, table_name, conn):
    columns = df.columns.tolist()
    col_types = ["TEXT" for _ in columns]
    cols_with_types = ", ".join(
        f'"{col}" {col_type}' for col, col_type in zip(columns, col_types)
    )
    create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols_with_types});'
    conn.execute(create_table_sql)

def main(max_files):
    r = requests.get("https://api.fda.gov/download.json")
    j = r.json()
    df = pd.DataFrame.from_dict(j)
    drug_urls = df.loc["drug"]
    files = drug_urls.loc["results"]
    events = files.get("event")
    events2 = events.get("partitions")

    i = 0
    for data_list in events2:
        print(data_list)
        url = data_list.get("file")
        data = requests.get(url)
        with open("output.zip", "wb") as fd:
            fd.write(data.content)
        with zipfile.ZipFile("output.zip") as zip_ref:
            zip_ref.extractall("target")
        
        i += 1
        if i >= max_files:
            break
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and process FDA data.")
    parser.add_argument(
        '--max_files',
        type=int,
        default=10,
        help='Maximum number of files to process (default: 10)'
    )
    args = parser.parse_args()
    main(args.max_files)