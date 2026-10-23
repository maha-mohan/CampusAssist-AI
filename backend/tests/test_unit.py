"""Fast unit tests: no database or network needed."""
from app.services import nlu
from app.services.ingestion import Page, chunk_pages, clean_pages
from app.services.llm_client import MockLLM
from app.services.prompts import build_context_block, user_prompt
from app.services.retrieval import RetrievedChunk, build_tsquery


def test_language_detection():
    assert nlu.detect_language("What is the fee for CSE?") == "en"
    assert nlu.detect_language("கட்டணம் எவ்வளவு?") == "ta"
    assert nlu.detect_language("Hostel fees evlo?") == "ta-en"
    assert nlu.detect_language("फीस कितनी है?") == "hi"


def test_intents():
    assert nlu.detect_intent("hi") == "greeting"
    assert nlu.detect_intent("Vanakkam") == "greeting"
    assert nlu.detect_intent("thank you so much") == "thanks"
    assert nlu.detect_intent("I want to raise a complaint") == "create_ticket"
    assert nlu.detect_intent("I have an issue with my exam hall ticket") == "create_ticket"
    assert nlu.detect_intent("can I talk to a staff member") == "create_ticket"
    assert nlu.detect_intent("status of ticket C20261017-001") == "ticket_status"
    # "hall ticket" is an exam document, not a support ticket
    assert nlu.detect_intent("How do I download my hall ticket?") == "question"
    assert nlu.detect_intent("What is the annual fee for CSE?") == "question"


def test_ticket_code_and_category():
    assert nlu.extract_ticket_code("my ticket is #c20261017-004 pls check") == "C20261017-004"
    assert nlu.guess_category("hall ticket not received for semester exam") == "Examination"
    assert nlu.guess_category("hostel room allocation") == "Hostel"
    assert nlu.guess_category("random thing") == "Other"


def test_tsquery_is_safe():
    q = build_tsquery("What's the fee for CSE?! ; DROP TABLE users;--")
    assert q and "'" not in q and ";" not in q
    assert "fee" in q and "cse" in q


def test_clean_pages_removes_headers_and_page_numbers():
    pages = [Page(i, f"ABC Engineering College\nContent line {i} with info\nPage {i} of 4") for i in range(1, 5)]
    cleaned = clean_pages(pages)
    assert all("ABC Engineering College" not in p.text for p in cleaned)
    assert all("Page" not in p.text for p in cleaned)
    assert "Content line 2" in cleaned[1].text


def test_chunking_splits_long_text():
    text = "\n\n".join(f"Paragraph {i}. " + "This sentence talks about admissions and fees. " * 20 for i in range(30))
    chunks = chunk_pages([Page(1, text)])
    assert len(chunks) > 3
    assert all(page == 1 for page, _ in chunks)


async def test_mock_llm_extractive_and_no_answer():
    chunk = RetrievedChunk(1, 1, "Fee Structure", "The annual tuition fee for CSE is ₹1,20,000.", None, None, "2026-27", "fees")
    prompt = user_prompt(build_context_block([chunk]), "What is the CSE fee?")
    llm = MockLLM()
    from app.services.llm_client import StreamResult
    out = "".join([t async for t in llm.stream([{"role": "user", "content": prompt}], StreamResult())])
    assert "1,20,000" in out and "[1]" in out
    prompt2 = user_prompt(build_context_block([chunk]), "Who won the cricket match?")
    out2 = "".join([t async for t in llm.stream([{"role": "user", "content": prompt2}], StreamResult())])
    assert out2 == "NO_ANSWER"


async def test_mock_embeddings_similarity():
    llm = MockLLM()
    a, b, c = await llm.embed(["hostel fee details", "what is the hostel fee", "placement companies list"])
    sim = lambda x, y: sum(i * j for i, j in zip(x, y))
    assert sim(a, b) > sim(a, c)
