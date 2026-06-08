# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->
     The domain is the dining hall menus, services and reviews at UCSD. This is useful because there are many dining halls around campus and with its extensive menu, it can tell the price of a dish and can help students make a decision of what to eat when they are meeting certain dietary concerns. For example someone may be wanting a certain type of meat or is craving a certain type of dish. Additionally, students may not be familiar with the Triton2Go option and it can help inform students about any questions with dining dollars.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 |Places to Eat at UCSD|PDF of Official Website|documents/Places to Eat at UCSD.pdf|
| 2 |Incoming Student Dining Plan
|Official Website|https://hdhdining.ucsd.edu/dining-plans/incoming.html|
| 3 |Continuing Student Dining Plan|Official Website|https://hdhdining.ucsd.edu/dining-plans/continuing.html|
| 4 |64 Degrees|Official Website|https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=64&subLocNum=00&locDetID=18&dayNum=0|
| 5 |Restaurants at Sixth College|Official Website|https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=37&subLocNum=00&locDetID=24&dayNum=0|
| 6 |Canyon Vista Marketplace|Official Website|https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=24&subLocNum=00&locDetID=11&dayNum=0|
| 7 |Ventanas|Official Website|https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=18&subLocNum=00&locDetID=8&dayNum=0|
| 8 |Triton2Go Mobile Ordering|Official Website|https://hdhdining.ucsd.edu/triton2go/index.html|
| 9 |Dining Accommodations|Official Website|https://hdhdining.ucsd.edu/nutrition-services/accommodations.html|
| 10 |Need food recommendations from dining halls.|UCSD Subreddit|https://www.reddit.com/r/UCSD/comments/1gsvgjl/need_food_recommendations_from_dining_halls/|

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**
- **Dining Plans (Incoming & Continuing Students):** 100 tokens per chunk, where 1 chunk = 1 plan option (e.g. Triton Gold, Triton Blue). These pages are structured like comparison tables with small, self-contained entries.
- **Menu Items (64 Degrees, Restaurants at Sixth College, Canyon Vista Marketplace, Ventanas):** 100–150 tokens per chunk, where 1 chunk = 1 menu item including name, station, allergens, dietary tags, and ingredients. Items are already atomic and self-contained.
- **Places to Eat (Blink page):** 60–100 tokens per chunk, where 1 chunk = 1 venue row including name, description (truncated to 1–2 sentences), location, hours (flattened), and accepted payments.
- **Triton2Go FAQ:** 100–200 tokens per chunk, where 1 chunk = 1 Q&A pair. Some answers are brief, others involve multi-step explanations (e.g. deposit refund edge cases).
- **Dining Accommodations:** 150–300 tokens per chunk, split on section boundaries (h2/h3 headers). Sections contain cohesive policy information that should not be split mid-thought.
- **Reddit Recommendations:** 30–100 tokens per chunk, where 1 chunk = 1 comment. If a reply is only intelligible in the context of its parent comment, the parent and reply are bundled as a single chunk.

**Overlap:**
No overlap for any source except Dining Accommodations, which uses a 1–2 sentence overlap between consecutive sections to preserve context that bleeds across section boundaries (e.g. pronouns or references that depend on the preceding section).

**Why these choices fit your documents:**
Dining plan entries are small and structured like a comparison table, so 1 plan = 1 chunk keeps each option retrievable independently. Menu items are already organized atomically by dish with consistent fields (name, allergens, ingredients, nutrition), so 1 item = 1 chunk avoids mixing unrelated dishes. The Blink Places to Eat page follows the same logic — 1 venue row = 1 chunk — though descriptions are truncated since station-level detail lives in the menu item chunks. Triton2Go content is a FAQ where each Q&A pair is self-contained, so pairing them avoids retrieving half an answer. Dining Accommodations is the only prose-heavy source where context can bleed across sections, justifying the small overlap. Reddit comments are individual opinions from different people, so merging them would corrupt retrieval; the only exception is threaded replies that are unintelligible without their parent.

**Final chunk count:**
1100
**5 Sample Chunks:**
Source type : menu
Chunk ID    : menu_0001
Source file : clean_menu.json
Text        : Farfalle Arrabbiata Primavera. Rotini pasta cooked with onions, broccoli, zucchini, and topped with an arrabbiata sauce and parmesan cheese.. Served at Al Dente, 64 Degrees. Meal: Lunch. Allergens: Contains Dairy, Contains Wheat, Contains Gluten. Dietary: Vegetarian, Sustainability. Calories: 543. P
------------------------------------------------------------

Source type : accommodations
Chunk ID    : accom_0001
Source file : clean_static_accommodations.json
Text        : Dining Accommodations
Our department dietitians are available for one-on-one consultations to discuss your food allergies or other dietary needs. To request a consultation, submit a request form or send an email to HDHdietitian@ucsd.edu. If you have food allergies or specific dietary restrictions th
------------------------------------------------------------

Source type : dining_plan
Chunk ID    : plan_0001
Source file : clean_static_incoming.json
Text        : Triton Gold: $8,200 ($6,700 Dining Dollars + $1,500 Triton Cash)
We recommend this plan if…
You enjoy three full meals a day during the school week, plus snacks in between classes
You plan to eat some meals off campus during the weekends
Daily Dining Dollar spend estimate: $27/day
------------------------------------------------------------

Source type : faq
Chunk ID    : faq_0001
Source file : clean_static_index.json
Text        : Q: Why is the Triton2Go container more sustainable than regular take-out?
A: Dining Services implemented this program in 2020 in order to help eliminate single use take-out containers and move us closer to the University’s Zero Waste goals.
------------------------------------------------------------

Source type : reddit
Chunk ID    : reddit_0001
Source file : clean_reddit.json
Text        : Ventanas is great, Soul has Chicken and Waffles and a Buffalo fried chicken plate I try to get when I see it. Can't go wrong with Ventanas imo, and shout out Nigerian chicken shawarma. You should also try the Oceanview pizza if you haven't. I'm a fan of Pines' huli-huli chicken too.
------------------------------------------------------------

Source type : places_to_eat
Chunk ID    : blink_0001
Source file : clean_blink.json
Text        : 64 Degrees. Good mood food (think burritos, sushi, burgers and milkshakes), private relaxation rooms, outdoor lounge space, and our Food Lab where you can learn how to make our culinary team’s favorite meals! Offering a modern vibe, choose from six stations featuring Triton Grill, Wok This Way, Taqu
---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:**
For the embedding model use all-MiniLM-L6-v2 via sentence-transformers.
**Retrieval Test:**
Query       : What dining plan should I get if I eat 1-2 meals a day?
Filter      : source_type=dining_plan
  Rank 1: [plan_0003 | clean_static_incoming.json] dist=0.5257
         Triton: $5,350 ($4,850 Dining Dollars + $500 Triton Cash)
We recommend this plan if…
Your dining routine is more spontaneous (i.e., a light lunch and hearty dinner one day, only breakfast and a light 
  Rank 2: [plan_0011 | clean_static_continuing.json] dist=0.5257
         Triton: $5,350 ($4,850 Dining Dollars + $500 Triton Cash)
We recommend this plan if…
Your dining routine is more spontaneous (i.e., a light lunch and hearty dinner one day, only breakfast and a light 
  Rank 3: [plan_0012 | clean_static_continuing.json] dist=0.5556
         Sun God Gold: $4,400 ($3,400 Dining Dollars + $1,000 Triton Cash)
We recommend this plan if…
A full meal a day during the school week (supplemented with snacks in between classes) keeps you fueled
You
------------------------------------------------------------

Query       : Where can I get poke on campus?
Filter      : source_type=None
  Rank 1: [blink_0042 | clean_blink.json] dist=0.4728
         Makai. Selection of Signature Poke bowls & BYO Poke Bar.. Hours: Mon-Thu: 8:00am-11:00am | Fri: 8:00am-8:00am | Sat: 10:00am-8:00am | Sun: 10:00am-11:00am. Payments accepted: Dining Dollars. Phone: 85
  Rank 2: [blink_0051 | clean_blink.json] dist=0.5835
         Restaurants at Sixth. College The Restaurants at Sixth College encompass five exciting and unique platforms as well as the largest retail market on campus. Enjoy plant- based entrees, poke bowls, all 
  Rank 3: [blink_0065 | clean_blink.json] dist=0.5863
         Starbucks. Enjoy your favorite iced or hot coffee and tea drinks at the student union.. Location: Price Center West. Hours: Mon-Thu: 7:00am-8:30pm | Fri: 7:00am-8:00pm | Sat: 7:00am-6:00pm | Sun: 9:00
  Rank 4: [blink_0082 | clean_blink.json] dist=0.5986
         The General Store. A non-profit, student run cooperative committed to offering the campus community with an assortment of school supplies, snacks, apparel, textbooks, and other convenience items at lo
  Rank 5: [reddit_0009 | clean_reddit.json] dist=0.6026
         Sounds like you need leave campus and make the pilgrimage to one of the most holiest sites in the area: The Taco Stand on Pearl St.
------------------------------------------------------------

Query       : What can I eat if I have a peanut allergy?
Filter      : source_type=accommodations
  Rank 1: [accom_0002 | clean_static_accommodations.json] dist=0.4218
         Food Allergies
If you have food allergies or specific dietary restrictions that require dining accommodations, you can register with the Office for Students with Disabilities (OSD) at osd.ucsd.edu. Al
  Rank 2: [accom_0003 | clean_static_accommodations.json] dist=0.5214
         Reduced Allergen Dining (RAD) Program
Although we do not use peanuts in our kitchens, there is no guarantee that cross-contact has not occurred in processing facilities outside of our kitchens. All st
  Rank 3: [accom_0004 | clean_static_accommodations.json] dist=0.5474
         Nutrition & Allergen Icons
For our menu offered to all students, visit our Online Dining app to review the full ingredients list and nutritional/allergen icons. Contains Dairy Contains Tree Nuts Conta
------------------------------------------------------------

Query       : What if I lose my Triton2Go container?
Filter      : source_type=faq
  Rank 1: [faq_0014 | clean_static_index.json] dist=0.3095
         Q: Can my friend return my Triton2Go reusable container for me?
A: You will need to return your container yourself and swipe your own Campus ID to get the funds returned to you.
  Rank 2: [faq_0016 | clean_static_index.json] dist=0.3594
         Q: What if the Triton2Go machine isn’t working?
A: If the Triton2Go machine is offline or not working, you will receive a token for your returned box. If you receive a token, take it to a manager or s
  Rank 3: [faq_0011 | clean_static_index.json] dist=0.3697
         Q: Why can’t I reuse my Triton2Go reusable container or my own reusable container after I have washed it myself?
A: For Health and Safety reasons, only properly cleansed and sanitized containers handl
------------------------------------------------------------

Query       : What is good at Ventanas?
Filter      : source_type=reddit
  Rank 1: [reddit_0004 | clean_reddit.json] dist=0.3786
         Ventanas any of the indian can’t go wrong imo
Bistro the tempura roll is good Pines korean pork yum yum bowl tho 🤤
  Rank 2: [reddit_0001 | clean_reddit.json] dist=0.4226
         Ventanas is great, Soul has Chicken and Waffles and a Buffalo fried chicken plate I try to get when I see it. Can't go wrong with Ventanas imo, and shout out Nigerian chicken shawarma. You should also
  Rank 3: [reddit_0002 | clean_reddit.json] dist=0.4755
         Original comment: Ventanas is great, Soul has Chicken and Waffles and a Buffalo fried chicken plate I try to get when I see it. Can't go wrong with Ventanas imo, and shout out Nigerian chicken shawarm
  Rank 4: [reddit_0006 | clean_reddit.json] dist=0.5412
         Original comment: I really like oyakodon chicken from pines with the yum yum sauce from the korean yum yum bowl. I really like ventanas, for breakfast I usually get the jalapeno biscuits and gravy pla
  Rank 5: [reddit_0005 | clean_reddit.json] dist=0.5770
         I really like oyakodon chicken from pines with the yum yum sauce from the korean yum yum bowl. I really like ventanas, for breakfast I usually get the jalapeno biscuits and gravy plate with scrambled 
**Production tradeoff reflection:**
The current chunk size for each page fits within the model because they all fall within the 256 context window, and majority of the conversations being held with the user are mostly questions to answer as conversational. There is not much analysis needed. Due to the smaller model, we will only be handling English the best compared to other languages. Due to the large amount of international students, their native language may not work as well. Analysis and interpretation of meals will not be too extensive for example, where a dish comes from or its origin. Additionally, with the smaller model trained on pre-existing text, it may not be familiar with UCSD specific terms like DD for dining dollars or Sixth representing Sixth College. This also heavily restricts on the wording of the query and content can easily get mixed up. Finally, when adding a new source, we will need to chunk it differently according to how much text it provides and the specificity of the information. 

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**
"You are a UCSD dining assistant. Answer only using the provided context. Do not use any outside knowledge. If the answer is not in the context, say exactly: I do not have that information in my current sources. Do not cite sources in your answer text — sources are handled separately."

**How source attribution is surfaced in the response:**
Instead of using RAG generation, we are using metadata to help source the information. When handling the query, the chunk_id is mapped to the source.

**Example Responses:**
Query: What can I eat if I have a peanut allergy?
------------------------------------------------------------
All of our dining locations are peanut-free. Peanuts are only sold pre-packaged in the markets. However, there is no guarantee that cross-contact has not occurred in processing facilities outside of our kitchens. If you have a peanut allergy, you can also consider registering with the Office for Students with Disabilities (OSD) and ordering meals from the RAD Menu, which is free from the FDA's Top 9 Allergens, including peanuts.

Retrieved from: clean_static_accommodations.json

============================================================
Query: Where can I get poke on campus?
------------------------------------------------------------
You can get poke at two locations on campus: Makai and The Restaurants at Sixth College. Both locations offer poke bowls.

Retrieved from: clean_blink.json, clean_reddit.json

============================================================
Query: What is the best CS professor at UCSD?
------------------------------------------------------------
I do not have that information in my current sources.

Retrieved from: clean_blink.json
---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 |I only eat 1–2 meals a day, what dining plan should I get?|Triton plan ($5,350) — lowest daily spend estimate at $20/day|I do not have that information in my current sources.|Off-target|Inaccurate|
| 2 |What is good at Ventanas?|Chicken and Waffles and a Buffalo fried chicken plate, and Indian Food|At Ventanas, the Indian options are good, and it's also mentioned that you can't go wrong with Ventanas in general.|Relevant|Accurate|
| 3 |Where can I get Poke?|Makai/Restaurants at Sixth College|You can get Poke at Makai.|Relevant|Accurate|
| 4 |What if I lose my to go container?|You will not be able to get your $5 deposit back for that container. You can continue to check out additional containers by paying the $5 refundable deposit.|If you lose your container, you will not be able to get your $5 deposit back for that container. You can continue to check out additional containers by paying the $5 refundable deposit.
|Relevant|Accurate|
| 5 |What can I get if I'm allergic to peanuts?|all dining locations are peanut-free; pre-packaged peanuts sold in markets only; cross-contact in outside facilities not guaranteed|All of our dining locations are peanut-free. Peanuts are only sold pre-packaged in the markets. If you have a peanut allergy and are registered with the Office for Students with Disabilities (OSD), you may also be eligible to order meals from the Reduced Allergen Dining (RAD) Menu, which is free from the FDA's Top 9 Allergens, including peanuts.
|Relevant|Accurate|

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**
I only eat 1–2 meals a day, what dining plan should I get?
**What the system returned:**
I do not have that information in my current sources.
**Root cause (tied to a specific pipeline stage):**
The query provided did not contain trigger words to retrieve the right information. It may be focusing on the meals part and the menu items may be the dominant data that drowns out the other options.
**What you would change to fix it:**
What I can do is changing the model to be a smarter one to have better inference on the context and including metadata to provide better trigger words for those chunks. They can be "incoming students", "freshman", "# of full/light meals".
---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**
With the extensive spec, it helped the program get the base RAG system working. Because it was split into multiple steps I can ask questions and verify each step so the next step is easier and produces the intended output. With the context of planning.md I can be more specific on the feature/implementation I need to focus on.
**One way your implementation diverged from the spec, and why:**
Originally when it helped create the website to interact with the ChatBot, it created 2 sections where 1 was the answer and the other was source. This was not what I wanted and had to tell it to incorporate the sources into the responses itself rather having a separate section. Additionally it was using the less readable file names as the sources and I had to tell it to map to names that are readable for UCSD users. I think this is because I just said add sources to the response without being specific enough of how to incorporate sources and what naming conventions it should use.
---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*
Read planning.md. I need a chunker.py that chunks my cleaned data 
according to the Chunking Strategy section.

Input files are in clean/:
- clean_menu.json
- clean_static_accommodations.json
- clean_static_continuing.json
- clean_static_incoming.json
- clean_static_index.json
- clean_reddit.json
- clean_blink.json

**Chunking rules per source type:**

1. clean_menu.json — 1 item = 1 chunk, no overlap
   Metadata: source_type, location, station, meal_period, date

2. clean_static_accommodations.json — split on h2/h3 section boundaries, 
   150-300 tokens, 1-2 sentence overlap between sections
   Metadata: source_type, section_heading

3. clean_static_incoming.json and clean_static_continuing.json — 
   1 plan option = 1 chunk, no overlap, ~60-100 tokens
   Metadata: source_type, plan_name, academic_year

4. clean_static_index.json (Triton2Go FAQ) — 1 Q&A pair = 1 chunk, 
   no overlap, 40-200 tokens
   Metadata: source_type, question

5. clean_reddit.json — 1 comment = 1 chunk, no overlap
   If is_reply is True and the parent comment is in the same file, 
   bundle parent + reply as one chunk
   Metadata: source_type, upvotes, date, is_reply_bundle

6. clean_blink.json — 1 venue = 1 chunk, no overlap, 60-100 tokens
   Metadata: source_type, venue_name, location, payments_accepted

**Output format for every chunk regardless of source:**
{
  "chunk_id": "unique string e.g. menu_0001",
  "text": "the chunk text formatted for embedding",
  "source": "original filename",
  "metadata": { ...source-specific fields above... }
}

Save all chunks to chunks/all_chunks.json as a single list.
Also print a summary: chunk count per source type and 
min/max/avg token count per source type.

- *What it produced:*
It helped me produce a file to chunk the clean data of the sources I have provided.
- *What I changed or overrode:*
N/A

**Instance 2**

- *What I gave the AI:*
How can I provide a detailed prompt to help me clean the scraped data extracted from the listed sites?
- *What it produced:*
Once you've verified what the raw data looks like, prompt Claude Code with the actual messy output:
Here is a sample of raw text extracted from the HDH accommodations page:

[paste the first 500 characters of your raw output here]

Clean this text by:
- Removing navigation menu items (lines like "Menus & Hours", "Events", "Student Jobs", "Toggle navigation")
- Removing the footer (UC San Diego address, copyright, accessibility links)
- Removing HTML entities like &amp; &nbsp; &lt;
- Keeping all substantive content: policy text, program descriptions, allergen info, contact emails

Write a `clean_static(text)` function that applies these rules.
The key is showing it your actual messy output rather than describing it abstractly — that way it writes cleaning rules that match your real data.

Once you run the scrapers and have raw JSON files, share what the output looks like here and we can verify together before moving to chunking. What source do you want to tackle first?
- *What I changed or overrode:*
I wanted to tackle the menus first as they were the main content.
