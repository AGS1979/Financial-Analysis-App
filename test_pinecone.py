import os
from pinecone import Pinecone

# --- CONFIGURATION ---
# Replace with your actual API key
PINECONE_API_KEY = "pcsk_4R2syU_EQCrzm8uj5gUJywUCQbN1eCw9XrEVZJXnNxAPet3vMV8n4Xg9Td2t4pvwu2DW5r" 
INDEX_NAME = "portfolio-agent" # The name of your index from the screenshot

# --- INITIALIZE CONNECTION ---
try:
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)
    print("✅ Successfully connected to Pinecone index.")
except Exception as e:
    print(f"❌ Error connecting to Pinecone: {e}")
    exit()

# --- PREPARE & UPSERT DATA ---
# Let's create a single sample vector to add.
# In your real app, this vector would come from your SentenceTransformer model.
sample_id = "doc1-chunk1"
sample_vector = [0.1] * 384 # A dummy 384-dimensional vector
sample_metadata = {
    "company": "TestCorp",
    "source_file": "test_document.pdf",
    "original_text": "This is a sample sentence from a test document."
}

print(f"\nAttempting to upsert a record with ID: {sample_id}")

try:
    # The upsert command sends your data to the index
    index.upsert(
        vectors=[
            (sample_id, sample_vector, sample_metadata)
        ]
    )
    print("✅ Upsert successful!")
except Exception as e:
    print(f"❌ Error during upsert: {e}")

# --- VERIFY THE RESULT ---
# You can check the number of records in your index to confirm the upsert
index_stats = index.describe_index_stats()
print(f"\nUpdated record count: {index_stats['total_record_count']}")