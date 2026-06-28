import os
import dotenv
from llama_parse import LlamaParse

# 1. Set your API key
dotenv.load_dotenv()
os.environ["LLAMA_CLOUD_API_KEY"] = os.getenv("LLAMA_CLOUD_API_KEY")

# 2. Configure the parser
parser = LlamaParse(
    result_type="markdown",  # Options: "markdown" or "text"
    num_workers=4,           # Number of workers for parallel processing
    verbose=True,
)

# 3. Parse the PDF document
# This returns a list of document objects (one per page or single combined)
documents = parser.load_data(r"data\Vijaya_Bank_vs_Prashant_B_Narnaware_on_14_May_2025.PDF")

# 4. Access the parsed Markdown content
for page_num, doc in enumerate(documents, start=1):
    print(f"--- Page {page_num} Markdown Content ---")
    print(doc.text)

# Combine all document pages into one text string
full_markdown = "\n\n".join([doc.text for doc in documents])

# Save to a file
with open("output.md", "w+", encoding="utf-8") as f:
    f.write(full_markdown)

print("Saved successfully to output.md!")