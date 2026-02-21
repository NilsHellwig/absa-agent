from typing import List, Optional
from pydantic import BaseModel, Field

# --- Retrieval & Filtering ---

class SearchQuery(BaseModel):
    optimized_query: str = Field(
        description="A concise and highly effective keyword-based search query formulated to find relevant review pages for the given research topic.")

class PageRelevanceResult(BaseModel):
    is_relevant: bool = Field(
        description="True if the webpage contains user-generated review content or links specifically about the subject, False if it is irrelevant.")

# --- Extraction ---

class Review(BaseModel):
    review_title: Optional[str] = Field(
        description="Title of the review", default=None)
    review_text: str = Field(description="Content of the review")
    stars: Optional[int] = Field(
        description="Star rating (usually 1-5)", default=None)

class ExtractionResult(BaseModel):
    reviews: List[Review] = Field(
        description="List of extracted reviews from the current page content")

class ReviewLinksDetection(BaseModel):
    urls: List[str] = Field(
        description="List of detected absolute or relative URLs that likely lead to more reviews (e.g. pagination or 'read more' links)")

# --- Repair ---

class RepairCheck(BaseModel):
    is_incomplete: bool = Field(
        description="True if the review is truncated/a snippet and needs reconstruction/completion, False if it is complete. Possible values: [true, false]")

class RepairSearch(BaseModel):
    search_term: str = Field(
        description="A substring from the current review snippet to locate its position in the HTML source code.")

class RepairResult(BaseModel):
    fixed_text: str = Field(
        description="The reconstructed original full text (verbatim) from the webpage source.")
    is_complete: bool = Field(
        description="True if the text is successfully reconstructed and complete, False if it remain truncated. Possible values: [true, false]")

# --- Verification ---

class ReviewVerification(BaseModel):
    is_authentic: bool = Field(
        description="True if the text is a individually-authored customer review reflecting personal opinion/experience, False if it is spam, neutral description, or irrelevant. Possible values: [true, false]")
