import pandas as pd
import json
import os
import sqlite3
import argparse
from dotenv import load_dotenv

def preprocess_dates(date_series):
    def convert_date(date):
        date_str = str(date)
        if len(date_str) == 8:
            try:
                return pd.to_datetime(date_str, format="%Y%m%d")
            except:
                pass
        elif len(date_str) == 6:
            try:
                return pd.to_datetime(date_str, format="%Y%m")
            except:
                pass
        elif len(date_str) == 4:
            try:
                return pd.to_datetime(date_str, format="%Y")
            except:
                pass
        return pd.NaT

    return date_series.apply(convert_date)

def clean_dataframe(df):
    """
    Convert columns containing dicts or lists to JSON strings.
    """
    for col in df.columns:
        if df[col].dtype == 'object':
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
    return df

input_data_dir = os.path.join(".", "target")

needed_drug_columns = [
    "safetyreportid",
    "medicinalproduct",
    "openfda.generic_name",
    "drugstartdate",
    "drugenddate",
    "drugindication",
]

needed_reaction_columns = ["safetyreportid", "reactionmeddrapt"]

needed_metadata_columns = [
    "safetyreportid",
    "receiptdate",
    "seriousnesshospitalization",
    "seriousnessdisabling",
    "seriousnessdeath",
    "seriousnesslifethreatening",
    "drugindication",
    "patientsex",
    "patientage",
    "patientageunit",
    "patientweight",
    "patientheight",
    "patientrace",
    "patientethnicgroup",
]

def main(max_files):
    data_list = []
    i = 0
    target_dir = input_data_dir  # Ensure this directory exists and contains JSON files
    if not os.path.exists(target_dir):
        print(f"Target directory '{target_dir}' does not exist.")
        return

    for filename in os.listdir(target_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(target_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    df = pd.json_normalize(data["results"])

                    # Process Reactions
                    reactions_temp = df[["safetyreportid", "patient.reaction"]]
                    reactions_temp = reactions_temp.explode("patient.reaction")
                    reactions_temp["reactionmeddrapt"] = reactions_temp[
                        "patient.reaction"
                    ].apply(
                        lambda x: x.get("reactionmeddrapt") if isinstance(x, dict) else None
                    )
                    reactions_temp = reactions_temp.drop(columns=["patient.reaction"])
                    reactions_temp = reactions_temp.dropna(subset=["reactionmeddrapt"])
                    reactions_temp = reactions_temp.reset_index(drop=True)
                    reactions_temp = clean_dataframe(reactions_temp)
                    reactions_temp = reactions_temp[needed_reaction_columns]

                    # Process Drugs
                    drugs_temp = df[["safetyreportid", "patient.drug"]]
                    drugs_temp = drugs_temp.explode("patient.drug")
                    drugs_temp_details = pd.json_normalize(drugs_temp["patient.drug"])
                    drugs_temp_details["safetyreportid"] = drugs_temp["safetyreportid"].values
                    drugs_temp_details["medicinalproduct"] = drugs_temp_details[
                        "medicinalproduct"
                    ].str.strip(".")
                    drugs_temp_details = drugs_temp_details.explode("openfda.generic_name")
                    drugs_temp_details["drugindication"] = drugs_temp_details[
                        "drugindication"
                    ].str.strip(".")

                    # Further Cleaning
                    columns_to_drop = [
                        col
                        for col in drugs_temp_details.columns
                        if "openfda." in col and "generic_name" not in col
                    ]
                    drugs_temp_details = drugs_temp_details.drop(
                        columns=columns_to_drop, errors="ignore"
                    )
                    drugs_temp_details["drugstartdate"] = preprocess_dates(
                        drugs_temp_details["drugstartdate"]
                    )
                    drugs_temp_details["drugenddate"] = preprocess_dates(
                        drugs_temp_details["drugenddate"]
                    )

                    drugs_temp_details = clean_dataframe(drugs_temp_details)
                    drugs_temp_details = drugs_temp_details[needed_drug_columns]

                    # Process Metadata
                    metadata_temp = df.drop(
                        columns=["patient.reaction", "patient.drug"], errors="ignore"
                    )
                    metadata_temp = metadata_temp.reset_index(drop=True)

                    metadata_temp["patientsex"] = df.get("patient.patientsex", None)
                    metadata_temp["patientage"] = df.get("patient.patientonsetage", None)
                    metadata_temp["patientageunit"] = df.get(
                        "patient.patientonsetageunit", None
                    )
                    metadata_temp["patientweight"] = df.get("patient.patientweight", None)
                    metadata_temp["patientheight"] = df.get("patient.patientheight", None)

                    metadata_temp["patientrace"] = df.get("patient.patientrace", None)
                    metadata_temp["patientethnicgroup"] = df.get(
                        "patient.patientethnicgroup", None
                    )

                    metadata_temp = clean_dataframe(metadata_temp)

                    for col in needed_metadata_columns:
                        if col not in metadata_temp.columns:
                            metadata_temp[col] = None

                    metadata_temp["receiptdate"] = preprocess_dates(
                        metadata_temp["receiptdate"]
                    )
                    metadata_temp = metadata_temp[needed_metadata_columns]

                    # Append to data lists
                    data_list.append({
                        "reactions": reactions_temp,
                        "drugs": drugs_temp_details,
                        "metadata": metadata_temp
                    })

                    i += 1
                    print(f"Processed file: {file_path}")

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {file_path}: {e}")
            except Exception as e:
                print(f"Unexpected error processing {file_path}: {e}")

            if i >= max_files:
                break

    if data_list:
        # Concatenate DataFrames
        reactions_df = pd.concat([d["reactions"] for d in data_list], ignore_index=True)
        drugs_df = pd.concat([d["drugs"] for d in data_list], ignore_index=True)
        metadata_df = pd.concat([d["metadata"] for d in data_list], ignore_index=True)

        print("Concatenated DataFrames created.")

        # Connect to SQLite
        conn = sqlite3.connect("data/fda_data.db")

        # Write Reactions
        reactions_df.to_sql("REACTIONS", conn, if_exists="append", index=False)
        print("Reactions data written to REACTIONS table.")

        # Write Drugs
        drugs_df.to_sql("DRUGS", conn, if_exists="append", index=False)
        print("Drugs data written to DRUGS table.")

        # Write Metadata
        metadata_df.to_sql("METADATA", conn, if_exists="append", index=False)
        print("Metadata written to METADATA table.")

        conn.close()
        print("Database connection closed.")
    else:
        print("No data files processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize FDA data.")
    parser.add_argument(
        '--max_files',
        type=int,
        default=10,
        help='Maximum number of files to process (default: 10)'
    )
    args = parser.parse_args()
    main(args.max_files)