import pandas as pd
import re

# === FILE NAMES ===
TOP50_FILE = "Top 50 Vendors-Grid view.csv"
FULL_FILE = "Full Database-Grid view.csv"
OUTPUT_FILE = "merged_pref_top50.csv"

# Canonical column names & order (NO YEAR FOUNDED)
COLUMNS = [
    "Vendor Name",
    "Vendor Overview",
    "Product Name",
    "Product Description",
    "Legal Functionality",
    "Functionality Sub-Category",
    "Main problem solved",
    "Primary User Segment",
    "Maturity Entry Level",
    "Regions Served",
    "AI Powered",
    "AI Platform Type",
    "Hosting Location",
    "Pricing Model",
    "Demo / Proof of Concept Available",
    "Adoption Level",
    "Ease of Purchase",
    "Deployment Model",
    "Industry Focus",
    "Languages Supported",
    "HQ",
    "Office Locations",
    "Hosting Provider",
    "ISO Certifications",
    "Security & Compliance Certifications",
    "Approx. Price Range (AUD)",
    "Customer Reviews",
    "Customer Feedback Rating",
    "Vendor Website",
    "Vendor Contact Details",
]

PRODUCT_COL = "Product Name"


def normalise_product_name(name: str) -> str:
    """Case-insensitive, punctuation-free key for product names."""
    if not isinstance(name, str):
        return ""
    name = name.strip().lower()
    name = re.sub(r"[^\w\s]", "", name)  # remove punctuation
    name = re.sub(r"\s+", " ", name)     # collapse multiple spaces
    return name


def align_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure df has all canonical columns; missing ones created as blank."""
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNS]  # enforce exact output order


def main():
    print("Loading CSV files...")
    top50 = pd.read_csv(TOP50_FILE)
    full = pd.read_csv(FULL_FILE)

    # Align schemas (ignore Year Founded entirely)
    top50 = align_columns(top50)
    full = align_columns(full)

    # Case-insensitive dedupe key
    top50["__ProductKey"] = top50[PRODUCT_COL].apply(normalise_product_name)
    full["__ProductKey"] = full[PRODUCT_COL].apply(normalise_product_name)

    # Combine with Top 50 first → Top 50 wins duplicates
    combined = pd.concat([top50, full], ignore_index=True)

    before = len(combined)
    deduped = combined.drop_duplicates(subset="__ProductKey", keep="first")
    after = len(deduped)

    print(f"Rows before dedupe: {before}")
    print(f"Rows after dedupe:  {after}")
    print(f"Duplicates removed: {before - after}")

    # Clean output
    deduped = deduped.drop(columns=["__ProductKey"])
    deduped = deduped[COLUMNS]  # exact order

    # Save final merged file
    deduped.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Merged file written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
