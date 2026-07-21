from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "raw" / "disaster_response_messages_training.csv"


df = pd.read_csv(DATA_PATH, low_memory=False)

print(f"Total messages: {len(df)}\n")


print(*df.columns.to_list(), sep=" ", end="\n\n")


aid_related_columns = [
    "medical_help",
    "medical_products",
    "search_and_rescue",
    "security",
    "child_alone",
    "water",
    "food",
    "shelter",
    "clothing",
    "missing_people",
    "refugees",
    "death",
]
df_aid = df[df[aid_related_columns].any(axis=1)]
print(f"Emergency aid related messages: {len(df_aid)}")
df["aids"] = df[aid_related_columns].apply(
    lambda row: row.index[row.eq(1)].tolist(), axis=1
)


hazards = ["floods", "storm", "fire", "earthquake", "cold"]
df_hazard = df[df[hazards].any(axis=1)]
print(f"Extreme weather related messages: {len(df_hazard)}")
df["hazards"] = df[hazards].apply(lambda row: row.index[row.eq(1)].tolist(), axis=1)

df_aid_hazard = df[df[aid_related_columns].any(axis=1) & df[hazards].any(axis=1)]
print(f"Both weather and aid related messages: {len(df_aid_hazard)}")

intents = ["request", "offer"]
df["intent"] = df[intents].apply(lambda row: row.index[row.eq(1)].tolist(), axis=1)


print(df["intent"].value_counts())
