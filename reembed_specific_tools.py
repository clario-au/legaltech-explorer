"""
Re-embed specific tools with enriched text that includes capability-specific
terminology not captured in their current product descriptions.

Run: python reembed_specific_tools.py
"""
import os, time
from dotenv import load_dotenv
load_dotenv(override=True)

from openai import OpenAI
from supabase import create_client

oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sb  = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# Tools to re-embed with enriched text.
# The enriched text ADDS capability keywords and ANZ terminology that are
# missing from the current product descriptions, improving retrieval for
# specific buyer-intent queries without fabricating features.
ENRICHMENTS = [
    {
        "vendor":  "Juro",
        "product": "Juro",
        "extra":   (
            "AI-native contract lifecycle management. Extract structured data points from "
            "existing contract populations including buy-side contracts, customer-side contracts, "
            "supplier agreements. Legacy contract import and bulk extraction. ARR extraction. "
            "CRM integration including HubSpot CRM. Contract repository. AI contract review. "
            "Data extraction from historical contract corpus."
        ),
    },
    {
        "vendor":  "Persuit",
        "product": "PERSUIT",
        "extra":   (
            "Legal panel RFP management. Competitive tendering for legal engagements. "
            "Outside counsel panel selection. Law firm panel management. Legal RFP platform. "
            "Request for proposal for legal services. Panel review and renewal. "
            "Competitive pitching and tendering workflow. Outside counsel selection and engagement. "
            "Legal procurement. Law firm benchmarking and selection."
        ),
    },
    {
        "vendor":  "Xakia",
        "product": "Xakia",
        "extra":   (
            "Legal operations management platform for in-house legal teams. "
            "Matter management. Legal intake and triage. Workflow management. "
            "In-house counsel productivity. Legal department management. "
            "Spend management. Outside counsel management. Legal analytics and reporting. "
            "ANZ legal operations. Australian legal technology. New Zealand legal ops. "
            "Legal operations SaaS. In-house legal team software."
        ),
    },
    {
        "vendor":  "Lawcadia",
        "product": "Lawcadia",
        "extra":   (
            "End-to-end legal operations platform for in-house legal teams and government. "
            "Matter management. Legal intake and triage. Outside counsel management. "
            "Legal panel management. Competitive tendering for legal services. "
            "Spend management. Law firm engagement and budgeting. "
            "Legal workflow and project management. Document management. "
            "ANZ legal operations. Australian legal technology. Queensland government legal. "
            "Corporate legal department SaaS. Legal marketplace."
        ),
    },
]

def build_base_text(tool: dict) -> str:
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

print("Re-embedding tools with enriched capability text...\n")

for e in ENRICHMENTS:
    # Fetch current tool data from Supabase
    res = sb.table("legal_tools").select("*").eq("Vendor Name", e["vendor"]).eq("Product Name", e["product"]).execute()
    if not res.data:
        print(f"NOT FOUND: {e['vendor']} / {e['product']}")
        continue

    tool = res.data[0]
    base_text    = build_base_text(tool)
    enriched_text = base_text + " | " + e["extra"]

    print(f"Re-embedding: {e['vendor']} / {e['product']}")
    print(f"  Base text:     {base_text[:120]}...")
    print(f"  Added:         {e['extra'][:120]}...")

    emb = oai.embeddings.create(model="text-embedding-3-small", input=enriched_text).data[0].embedding

    sb.table("legal_tools").update({"embedding": emb}) \
        .eq("Vendor Name", e["vendor"]) \
        .eq("Product Name", e["product"]) \
        .execute()

    print(f"  Updated in Supabase.\n")
    time.sleep(0.5)

print("Done. Run test_search.py to validate.")
