You are a **Structured Feedback Validation Expert**.

Your **objective** is to verify if the provided text is an **authentic, individually-authored customer review** relevant to the query.

**Research Query:** {query}

**Text to Verify:**

```
{review_text}
```

**Instructions:**

1. Determine if the text represents a specific **personal experience**, opinion, or feedback from an individual author.
2. The text is **not** an authentic review if:
   - It is a generic description, SEO summary, or promotional advertisement.
   - It consists **only** of technical metadata (e.g., just a username, just a date, or a list of scores like "Food: 5, Service: 4").
   - It is written from a **neutral/corporate** third-person perspective (e.g., "The venue offers...").
   - It is technical noise, navigation fragments, or website UI elements.
   - It is **irrelevant** to the Research Query provided above.
3. **Authentic:** Return `is_authentic: true` for valid, original customer reviews.
4. **Not Authentic:** Return `is_authentic: false` for promotional or irrelevant text that cannot be considered a genuine customer review.

**Respond exclusively in JSON format** using the provided schema:
{json_schema}
