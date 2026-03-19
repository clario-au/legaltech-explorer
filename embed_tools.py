"""
embed_tools.py
One-time (and re-runnable) script to generate OpenAI embeddings for every
tool in the legal_tools Supabase table and store them in the embedding column.

Usage:
    python embed_tools.py

Requires SUPABASE_URL, SUPABASE_SERVICE_KEY, and OPENAI_API_KEY in .env
"""

import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

EMBED_MODEL = "text-embedding-3-small"  # 1536 dims, cheap, high quality
BATCH_SIZE = 20                          # OpenAI allows up to 2048 inputs per call
SLEEP_BETWEEN_BATCHES = 1.0             # seconds — stay well under rate limit


def build_embedding_text(tool: dict) -> str:
    """
    Concatenate the most semantically rich fields into a single string
    for embedding. Omit empty values.
    """
    fields = [
        tool.get("Product Name", ""),
        tool.get("Vendor Name", ""),
        tool.get("Product Description", ""),
        tool.get("Vendor Overview", ""),
        tool.get("Legal Functionality", ""),
        tool.get("Functionality Sub-Category", ""),
        tool.get("Main problem solved", ""),
        tool.get("Primary User Segment", ""),
        tool.get("Industry Focus", ""),
        tool.get("AI Platform Type", ""),
    ]
    return " | ".join(f for f in fields if f and str(f).strip())


def main():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        return
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY must be set in .env")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    openai = OpenAI(api_key=OPENAI_API_KEY)

    # Fetch all tools
    print("Fetching tools from Supabase...")
    response = supabase.table("legal_tools").select("*").execute()
    tools = response.data
    print(f"Found {len(tools)} tools.")

    # Only embed tools that don't have an embedding yet (allows safe re-runs)
    to_embed = [t for t in tools if not t.get("embedding")]
    already_done = len(tools) - len(to_embed)
    if already_done:
        print(f"{already_done} tools already embedded, skipping.")
    print(f"Embedding {len(to_embed)} tools...")

    total = len(to_embed)
    embedded = 0
    errors = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = to_embed[batch_start:batch_start + BATCH_SIZE]
        texts = [build_embedding_text(t) for t in batch]

        try:
            embed_response = openai.embeddings.create(
                model=EMBED_MODEL,
                input=texts
            )
        except Exception as e:
            print(f"  ERROR: OpenAI embedding call failed for batch {batch_start}: {e}")
            errors += len(batch)
            time.sleep(2)
            continue

        for i, tool in enumerate(batch):
            vector = embed_response.data[i].embedding
            vendor = tool.get("Vendor Name", "")
            product = tool.get("Product Name", "")

            try:
                supabase.table("legal_tools").update(
                    {"embedding": vector}
                ).eq("Vendor Name", vendor).eq("Product Name", product).execute()
                embedded += 1
            except Exception as e:
                print(f"  ERROR: Failed to update {vendor} / {product}: {e}")
                errors += 1

        print(f"  Progress: {min(batch_start + BATCH_SIZE, total)}/{total} tools processed")
        time.sleep(SLEEP_BETWEEN_BATCHES)

    print(f"\nDone. {embedded} embedded successfully, {errors} errors.")
    if errors:
        print("Re-run the script to retry failed tools (already-embedded tools are skipped).")


if __name__ == "__main__":
    main()
