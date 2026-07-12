from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# 1. Configure Presidio to use the SMALL, RAM-friendly SpaCy model
configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
}

# 2. Initialize the engines
provider = NlpEngineProvider(nlp_configuration=configuration)
nlp_engine = provider.create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
anonymizer = AnonymizerEngine()

def scrub_pii(text: str) -> str:
    """
    Detects and redacts PII (Names, Emails, Phone Numbers) using a lightweight NLP model.
    """
    if not text:
        return ""
        
    # Analyze the text for PII entities
    results = analyzer.analyze(text=text, entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", 'EMPLOYEE', 'OFFICE' ], language='en')
    
    # Anonymize the text based on the findings
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    
    return anonymized_result.text