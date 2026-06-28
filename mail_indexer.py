import re
from datetime import datetime
import pypdf

# def extract_text_from_pdf(pdf_path):
#     """Extracts raw text from the provided PDF file."""
#     reader = pypdf.PdfReader(pdf_path)
#     full_text = ""
#     for page in reader.pages:
#         full_text += page.extract_text() + "\n"
#     return full_text

def extract_text_from_pdf(pdf_path):
    """Extracts raw text from the provided PDF file."""
    reader = pypdf.PdfReader(pdf_path)
    return "".join(page.extract_text() + "\n" for page in reader.pages)


# def parse_and_deduplicate_emails(raw_text):
#     """
#     Parses the massive block of raw text, splits it into distinct emails,
#     cleans up the repetitive 'On [Date], X wrote:' trail duplicates,
#     and returns a chronologically sorted list of unique emails.
#     """
#     # Pattern to identify individual email headers in common formats
#     # This captures variations of email boundaries like 'From:', 'Sat, 30 May 2026...', etc.
#     email_blocks = re.split(r'(?=From: |Date: |Subject: |^[A-Za-z\s]+ < [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,} >)', raw_text, flags=re.MULTILINE)
    
#     parsed_emails = []
#     seen_contents = set()  # Used to avoid duplicating identical body components
    
#     for block in email_blocks:
#         if not block.strip():
#             continue
            
#         # 1. Parse meta details safely using regex
#         from_match = re.search(r'(?:From:\s*|^\b)(.+?<.+?>)', block, re.MULTILINE)
#         date_match = re.search(r'Date:\s*(.+)|(?:Sat|Sun|Mon|Tue|Wed|Thu|Fri),\s*(\d{2}\s+[A-Za-z]+\s+\d{4}.+)', block)
#         subject_match = re.search(r'Subject:\s*(.+)', block)
        
#         # Clean metadata extractions
#         sender = from_match.group(1).strip() if from_match else "Unknown Sender"
        
#         email_date_str = ""
#         if date_match:
#             email_date_str = (date_match.group(1) or date_match.group(2)).strip()
            
#         subject = subject_match.group(1).strip() if subject_match else "Re: Email Chain"
        
#         # 2. Extract Body and chop off the trailing repeated threads
#         # Splits right at the common "On Wed, Apr 22... wrote:" line
#         body_cleaned = re.split(r'(On\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun).+?wrote:)', block, flags=re.IGNORECASE)[0]
#         # Also clean up standard block metadata headers inside the body
#         body_cleaned = re.split(r'(From:\s*|To:\s*|Cc:\s*|Date:\s*)', body_cleaned)[0]
        
#         # Balance spacing and strip noise
#         body_cleaned = body_cleaned.replace(sender, "").replace(subject, "").replace(email_date_str, "")
#         body_cleaned = re.sub(r'(To|Cc):\s*".+?"\s*<.+?>', '', body_cleaned) # Clear raw recipient lists
#         body_cleaned = body_cleaned.strip()
        
#         # Create a unique fingerprint hash of the text body to verify uniqueness
#         content_fingerprint = re.sub(r'\s+', '', body_cleaned.lower())
        
#         if content_fingerprint and content_fingerprint not in seen_contents and len(body_cleaned) > 5:
#             seen_contents.add(content_fingerprint)
            
#             # Try parsing date to accurately sort chronologically later
#             timestamp = datetime.min
#             if email_date_str:
#                 try:
#                     # Clean generic timezone variations (+0530) for parsing ease
#                     clean_date_str = re.sub(r'\s*\([^)]*\)', '', email_date_str)
#                     clean_date_str = re.sub(r'([+-]\d{4})', '', clean_date_str).strip()
#                     # Example layout match: "30 May 2026 6:28:38 PM" or "Sat, 02 May 2026 12:12:53"
#                     timestamp = datetime.strptime(clean_date_str, "%a, %d %b %Y %H:%M:%S")
#                 except Exception:
#                     try:
#                         timestamp = datetime.strptime(clean_date_str, "%d %b %Y %I:%M:%S %p")
#                     except Exception:
#                         pass # Fallback to base datetime if variation fails
            
#             parsed_emails.append({
#                 'sender': sender,
#                 'date': email_date_str,
#                 'timestamp': timestamp,
#                 'subject': subject,
#                 'body': body_cleaned
#             })
            
#     # Sort chronologically (oldest to newest)
#     parsed_emails.sort(key=lambda x: x['timestamp'])
#     return parsed_emails

def parse_and_deduplicate_emails(raw_text):
    """
    Parses structural blocks using a Subtraction Matrix to prevent linear truncation data loss.
    """
    # 1. Block Array Split
    email_blocks = re.split(
        r'(?m)(?=^From:\s|^Date:\s|^Subject:\s|^[A-Za-z\s.-]+ <\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*>)', 
        raw_text
    )
    
    parsed_emails = []
    seen_contents = set()
    
    for block in email_blocks:
        if not block.strip():
            continue
            
        # --- METADATA EXTRACTION ---
        sender_match = re.search(r'(?:From:\s*|^)([A-Za-z\s.-]+ <\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*>)', block, re.MULTILINE)
        sender = sender_match.group(1).strip() if sender_match else "Unknown Sender"
        
        # Bounded regex targetting DD Month YYYY or Month DD, YYYY
        date_match = re.search(
            r'(Date:\s*.+|(?:Sat|Sun|Mon|Tue|Wed|Thu|Fri),\s*(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},\s+\d{4}).+?(?:\d{1,2}:\d{2}\s*(?:AM|PM)?|\d{4}))', 
            block, re.IGNORECASE
        )
        email_date_str = date_match.group(1).strip() if date_match else ""
        
        subj_match = re.search(r'^Subject:\s*(.+)$', block, re.MULTILINE)
        subject = subj_match.group(1).strip() if subj_match else "Re: Email Chain"
        
        # --- BODY ISOLATION (SUBTRACTION MATRIX) ---
        body_cleaned = block
        
        # Phase 1: Truncate deduplication tails based on variable signatures
        body_cleaned = re.split(
            r'(?i)(On\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun).+?wrote:|\[Quoted text hidden\]|\d{2}\.\d{2}\.\d{4},\s*\d{2}:\d{2}.+?:)', 
            body_cleaned
        )[0]
        
        # Phase 2: Systematically subtract known metadata entities
        body_cleaned = re.sub(r'^(?:To|Cc):\s*.*?$', '', body_cleaned, flags=re.MULTILINE)
        body_cleaned = body_cleaned.replace(sender, "")
        
        if email_date_str:
            body_cleaned = body_cleaned.replace(email_date_str, "")
        if subj_match:
            body_cleaned = body_cleaned.replace(subj_match.group(0), "")
            
        # Phase 3: Vacuuming whitespace and normalizing
        body_cleaned = body_cleaned.strip()
        
        # --- METRICS & HASHING ---
        content_fingerprint = re.sub(r'\s+', '', body_cleaned.lower())
        
        if content_fingerprint and content_fingerprint not in seen_contents and len(body_cleaned) > 5:
            seen_contents.add(content_fingerprint)
            
            timestamp = datetime.min
            if email_date_str:
                clean_date_str = re.sub(r'^(Date:\s*)', '', email_date_str, flags=re.IGNORECASE)
                clean_date_str = re.sub(r'\s*\([^)]*\)', '', clean_date_str)
                clean_date_str = re.sub(r'([+-]\d{4}|at\s)', '', clean_date_str).strip()
                
                formats = [
                    "%a, %d %b %Y %H:%M:%S",
                    "%d %b %Y %I:%M:%S %p",
                    "%a, %b %d, %Y %I:%M %p" 
                ]
                for fmt in formats:
                    try:
                        timestamp = datetime.strptime(clean_date_str, fmt)
                        break
                    except ValueError:
                        pass
            
            parsed_emails.append({
                'sender': sender,
                'date': email_date_str,
                'timestamp': timestamp,
                'subject': subject,
                'body': body_cleaned
            })
            
    parsed_emails.sort(key=lambda x: x['timestamp'])
    return parsed_emails

def generate_markdown(emails):
    """Converts the sorted email structural dictionary data into crisp Markdown files."""
    markdown_output = "# Cleaned Email Chain Transcript\n\n"
    
    for idx, email in enumerate(emails, 1):
        markdown_output += f"### Email {idx}\n"
        markdown_output += f"* **From:** `{email['sender']}`\n"
        markdown_output += f"* **Date:** {email['date']}\n"
        markdown_output += f"* **Subject:** {email['subject']}\n\n"
        markdown_output += f"{email['body']}\n\n"
        markdown_output += "---\n\n"
        
    return markdown_output

# --- execution entrypoint ---
if __name__ == "__main__":
    # Specify the path to your source email chain PDF
    pdf_input_file = "mailchain_tanisha.pdf" 
    output_md_file = "cleaned_transcript_" + pdf_input_file.replace(".pdf", ".md")
    
    try:
        raw_text = extract_text_from_pdf(pdf_input_file)
        unique_emails = parse_and_deduplicate_emails(raw_text)
        markdown_content = generate_markdown(unique_emails)
        
        with open(output_md_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        print(f"Success! Processed {len(unique_emails)} unique emails into '{output_md_file}'")
    except Exception as e:
        print(f"An error occurred: {e}")