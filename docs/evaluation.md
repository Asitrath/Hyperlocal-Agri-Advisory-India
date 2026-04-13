# 📊 System Evaluation & Test Logs

## Evaluation Summary (April 8, 2026)

### 📈 Metrics
| Query | Top Result Score | Location Accuracy | Content Relevance | Status |
| :--- | :--- | :--- | :--- | :--- |
| Rice Pest (Odisha) | 0.485 | ✅ Correct | ✅ High (Pesticides listed) | PASS |
| Drought (Pune) | 0.704 | ⚠️ Mixed (Nasik) | ✅ High (Strategies) | PASS |
| Kharif (Bihar) | 0.813 | ✅ Correct | ✅ High (Sowing windows) | PASS |
| Apples (Chennai) | N/A | ✅ N/A | ✅ Correct Refusal | PASS (Guardrail) |

### 💡 Key Findings
1. **Locality Bias:** General terms like "Drought" sometimes outweigh specific district names in vector search. **Action:** Recommended using the `--state` filter for high-precision queries.
2. **Guardrail Success:** The system now correctly identifies queries outside the ICAR-CRIDA scope and refuses to provide "general knowledge" hallucinations.
3. **Chunking Performance:** 1500-token chunks are effectively preserving table-row relationships, providing actionable chemical dosages.

---

## 🧪 Detailed Test Results

### Test 1: Rice Pest Management (Odisha)
- **Query:** "Stem borer control chemical for rice in Odisha"
- **Response:** Recommended **Methyl demeton/Dimethioate** based on Sundargarh and Boudh plans.
- **Status:** ✅ SUCCESS. Accurate technical extraction.

### Test 2: Delayed Monsoon (Bihar)
- **Query:** "What should I grow if monsoon is delayed by 4 weeks in Patna?"
- **Response:** Suggested short-duration varieties like **Prabhat, Dhanlaxmi, and Richharia**. Also noted Pigeonpea varieties (Bahar, Narendra).
- **Status:** ✅ SUCCESS. Successfully mapped "4 weeks" to "Late Sowing" contingency measures.

### Test 3: Out-of-Distribution / Safety (Chennai Apples)
- **Query:** "How do I grow apples in Chennai?"
- **Initial Result:** ❌ FAILED (Hallucinated general advice about Shimla/Ooty).
- **Post-Fix Result:** ✅ **SUCCESS (Refusal).** The system stated: *"I am sorry, but the official ICAR-CRIDA contingency plans for this specific query are not in my database."*
- **Observation:** Demonstrates that the strict System Prompt is preventing dangerous out-of-context advice.

### Test 4: Drought Contingency (Maharashtra)
- **Query:** "Drought management for Solapur Maharashtra"
- **Response:** Identified **Pearl Millet** as a drought-hardy alternative for shallow black soils. Suggested protective irrigation and interculturing.
- **Status:** ✅ SUCCESS. 

### Test 5: Chemical Dosages (Bihar)
- **Query:** "Pesticide for BLB in rice Patna"
- **Response:** Recommended **Streptocycline** spray combined with copper fungicides as per Arwal/Patna district protocols.
- **Status:** ✅ SUCCESS. High specificity on dosage and timing.

### Test 6: Irrelevant Query (General)
- **Query:** "Who is the Prime Minister of India?"
- **Response:** *"I am sorry, but I am a strict agricultural advisor. I only provide information based on ICAR-CRIDA agricultural documents."*
- **Status:** ✅ SUCCESS (Guardrail). Correctly ignored non-farming query.

### Test 7: State Filtering Test
- **Query:** `@Bihar flood contingency measures`
- **Response:** Provided specific advice for **Saharsa and Munger** regarding shallow water maintenance in nurseries and drainage.
- **Status:** ✅ SUCCESS. Metadata filtering confirmed working.

## 🧪 Phase 4: Weather-Aware Evaluation (April 10, 2026)

This phase evaluates the system's ability to synthesize real-time API data (Open-Meteo) with static ICAR-CRIDA contingency plans.

### 📈 Updated Metrics
| Query | Top Result Score | Weather Context | LLM Synthesis | Status |
| :--- | :--- | :--- | :--- | :--- |
| Irrigation (Patna) | 0.698 | ☀️ Severe Deficit | ✅ Advised life-saving irrigation | **PASS** |
| Sowing (Solapur) | 1.296 | 🔥 High ET0 (6.8mm) | ✅ Prioritized moisture conservation | **PASS** |
| Weather (New York) | N/A | 🚫 Out of Bounds | ✅ Correct Refusal | **PASS** |

### 💡 Phase 4 Key Findings
1.  **Dynamic Decision Support:** The system successfully identifies **Severe Deficit** rainfall patterns via the Open-Meteo API and triggers the "Drought" and "Mid-season dry spell" sections of the contingency plans.
2.  **Synthesis Quality:** In the Patna test, the LLM correctly linked the live 0.0mm forecast to the ICAR recommendation for **life-saving irrigation**.
3.  **Coordinate Guardrails:** The system properly refuses queries for locations outside the predefined `DISTRICT_COORDS` (e.g., New York), maintaining its focus on Indian agriculture.

---

## 🧪 Detailed Weather-Aware Test Results

### Test 8: Real-Time Drought Synthesis (Patna)
* **Query:** "Should I irrigate my rice crop in Patna today?"
* **API Context:** 33.3°C, 1.1mm past rain, 0.0mm forecast (**Severe Deficit**).
* **Response:** The system advised prioritizing **life-saving irrigation** today to ensure crop survival, specifically citing Document 1 (Page 21) regarding low rainfall and delayed canal water.
* **Status:** ✅ **SUCCESS.** The system effectively cross-referenced static document needs with critical live deficits.

### Test 9: High Evapotranspiration Analysis (Solapur)
* **Query:** "Sowing advice for Solapur given current conditions."
* **API Context:** 38.9°C, 0.0mm rain, **ET0: 6.8mm (High Demand)**.
* **Response:** Recommended **drought-tolerant crops** (Paddy via Dapog method or Soybean) and specific moisture conservation measures like thinning and gap filling through hoeing to reduce water loss.
* **Status:** ✅ **SUCCESS.** The high ET0 value correctly influenced the AI to focus on agronomic measures for moisture retention.

### Test 10: Boundary & Irrelevance Test (New York)
* **Query:** `/weather New York` or `"weather in New York"`
* **System Action:** Correctly identified that the district is not in the database and that no relevant agricultural documents exist for this region.
* **Status:** ✅ **SUCCESS.** Verified that the weather module and document retrieval are strictly bounded to the 5 targeted Indian states.

## 🧪 Phase 5: Telegram Bot & UX Evaluation (April 10, 2026)

This phase tests the transition from a terminal-based CLI to a mobile-first Telegram interface, focusing on user interaction, state persistence, and mobile readability.

### 📈 Interface Metrics
| Feature | Target | Result | Status |
| :--- | :--- | :--- | :--- |
| **Response Latency** | < 15s | ~8-12s (Ollama/Mistral) | ✅ PASS |
| **Mobile Readability** | < 300 words | 150-240 words avg. | ✅ PASS |
| **State Persistence** | `/state` works | User filter remains active | ✅ PASS |
| **Markdown Accuracy** | No parsing errors | Code blocks render correctly | ✅ PASS |

### 💡 Key UX Findings
1. **Typing Indicators:** The addition of `send_action("typing")` significantly improved the perceived speed of the bot, reducing user abandonment during the RAG retrieval window.
2. **Concise Prompting:** The 300-word constraint in the `SYSTEM_PROMPT` successfully forced the LLM to provide bulleted, actionable advice rather than dense paragraphs.
3. **Threshold Guardrails:** The `SCORE_THRESHOLD = 1.0` successfully prevented "hallucinated document matches" for out-of-scope queries (e.g., Apple farming in Chennai).

---

## 🧪 Telegram Interaction Logs

### Test 11: Real-Time Advisory (Muzaffarpur)
* **Query:** "What crops for delayed monsoon in Muzaffarpur?"
* **Bot Action:** Fetched live weather -> Identified 2-week delay context -> Retrieved Bihar PDFs.
* **Output:** Recommended rice varieties (**Rajshree, Santosh**) and upland alternatives (**Rice-Pigeonpea**). Successfully cited Document 1, 2, and 4.
* **Status:** ✅ **SUCCESS.** The "Weather + RAG" synthesis provided a localized, time-sensitive recommendation.

### Test 12: Session Persistence (@State Filter)
* **Command:** `/state Bihar`
* **Follow-up Query:** "How do I grow apples in Chennai?"
* **Bot Action:** Applied Bihar filter -> Searched database -> Found no matches.
* **Output:** *"The ICAR-CRIDA contingency plans in my database do not have relevant information for this query. I cover districts in: Bihar, Odisha, Maharashtra, Rajasthan, and Andhra Pradesh."*
* **Status:** ✅ **SUCCESS.** Confirmed that the bot correctly restricts its knowledge base and refuses out-of-distribution queries without hallucinating.

### Test 13: Direct Weather Access
* **Command:** `/weather Patna`
* **Output:** Rendered a formatted weather table showing **SEVERE DEFICIT** rainfall and **High ET0** (6.1mm).
* **Status:** ✅ **SUCCESS.** Verified that the weather module can be used as a standalone diagnostic tool for farmers.

## 🧪 Phase 6: Government Scheme & Policy Evaluation (April 10, 2026)

This phase evaluates the system's ability to retrieve procedural and financial information from National Schemes (PM-KISAN, PMFBY, RKVY) using the new `doc_type: scheme` metadata tag.

### 📈 Policy Metrics
| Query | Top Result Score | Source Category | Answer Accuracy | Status |
| :--- | :--- | :--- | :--- | :--- |
| PM-KISAN Eligibility | 0.421 | `_schemes` | ✅ Correct (Step-by-step) | **PASS** |
| PMFBY Kharif Premium| 0.588 | `_schemes` | ✅ Correct (2% rate) | **PASS** |
| Aadhaar Failure | 0.612 | `_schemes` | ✅ Correct (Edit portal) | **PASS** |

### 💡 Phase 6 Key Findings
1. **Procedural Precision:** The LLM successfully extracted step-by-step UI instructions (e.g., "Farmers Corner" -> "Edit Aadhaar Failure Record"), showing that the larger 1500-token chunks are capturing technical workflows effectively.
2. **Metadata Power:** By tagging documents with `scheme: PMFBY` or `scheme: PM-KISAN`, the retrieval engine is prioritizing the correct policy document over general district mentions.
3. **Financial Awareness:** The system accurately identified the 2% Kharif premium for Rice, a critical piece of data for farmer financial planning.

---

## 🧪 Phase 6: Government Scheme & Policy Evaluation (April 10, 2026)

This phase evaluates the system's ability to retrieve procedural and financial information from National Schemes (PM-KISAN, PMFBY, RKVY) using the new `_schemes` ingestion logic.

### 📈 Policy Metrics
| Query | Top Result Score | Source Category | Answer Accuracy | Status |
| :--- | :--- | :--- | :--- | :--- |
| PM-KISAN Eligibility | 0.421 | `_schemes` | ✅ Correct (Step-by-step) | **PASS** |
| PMFBY Kharif Premium| 0.588 | `_schemes` | ✅ Correct (2% rate) | **PASS** |
| Aadhaar Failure | 0.612 | `_schemes` | ✅ Correct (Edit portal) | **PASS** |

### 💡 Phase 6 Key Findings
1. **Procedural Precision:** The LLM successfully extracted step-by-step UI instructions (e.g., "Farmers Corner" -> "Edit Aadhaar Failure Record"), showing that the 1500-token chunks are capturing technical workflows effectively.
2. **Metadata Enrichment:** The ingestion-side schema successfully tagged documents with `scheme: PMFBY` or `scheme: PM-KISAN`, allowing the model to cite the correct policy source.
3. **Financial Awareness:** The system accurately identified the 2% Kharif premium for Rice, a critical piece of data for farmer financial planning.

---

## 🧪 Detailed Policy Test Results

### Test 14: Procedure for PM-KISAN Status
* **Query:** "Am I eligible for PM-KISAN?"
* **Response:** Detailed the exact 5-step process on the `pmkisan.gov.in` portal, including clicking "Farmers Corner" and entering the Aadhaar number.
* **Status:** ✅ SUCCESS.

### Test 15: PMFBY Financial Logic (Kharif Rice)
* **Query:** "What premium do I pay for rice insurance in kharif?"
* **Response:** Correctly identified the **2% Sum Insured** rate for Kharif crops. It also explained the "Sum Insured" formula (Scale of Finance x Area), providing actionable financial context.
* **Status:** ✅ SUCCESS.

### Test 16: Handling Edge Cases (Lost Aadhaar)
* **Query:** "How to apply for PM-KISAN if I lost my Aadhaar?"
* **Response:** Successfully retrieved the "Edit Aadhaar Failure Record" workflow. This proves the RAG system can handle troubleshooting queries, not just general info.
* **Status:** ✅ SUCCESS.

## 🤖 Automated Evaluation Report (April 10, 2026)

### Summary Statistics
* **Total Tests:** 5
* **Pass Rate:** 60% (3/5)
* **Average Latency:** 18.57s
* **Max Latency:** 42.58s (Weather-Aware)

### Identified Regressions
* **TC02 (Contingency):** Returned Null. Investigation required into ChromaDB score thresholding for Solapur district.
* **TC04 (Guardrail):** Minor hallucination regarding state boundaries (Chennai/Andhra). Prompt engineering needed to tighten geographic strictly.

### Successes
* **Scheme Integration:** High accuracy on PMFBY premiums and PM-KISAN troubleshooting.
* **Weather Synthesis:** Successfully mapped real-time Patna drought signals to specific ICAR seed recommendations.

# Agriculture RAG — Evaluation Report
**Date:** 2026-04-13 10:48
**Model:** mistral
**Test cases:** 10

## Summary
| Metric | Value |
|--------|-------|
| Average Score | **4.3 / 5** |
| Pass Rate (>=3) | **10/10** |
| Perfect (5/5) | **4/10** |
| Failures (<=1) | **0/10** |

## Scores by Category
| Category | Avg Score | Tests |
|----------|-----------|-------|
| Contingency | 4.3 / 5 | 3 |
| Cross-District | 4.0 / 5 | 1 |
| Guardrail | 4.0 / 5 | 2 |
| Schemes | 4.5 / 5 | 2 |
| Weather-Aware | 4.5 / 5 | 2 |

## Detailed Results

### ✅ TC01: Should I irrigate my rice crop in Patna today?
**Category:** Weather-Aware | **Score:** 5/5 | **Latency:** 29.51s

**Expected:** Identify rainfall deficit from live data and recommend life-saving irrigation.

**Keyword Check:** All keywords OK

**Grading Reason:** The response directly addresses the query, meets the goal, and cites specific districts/data.

>  In Patna, Bihar, the current situation is severe deficit rainfall with high evapotranspiration. The official ICAR-CRIDA contingency plans suggest life saving irrigation for rice crops in such conditions.
> 
> For rice, consider varieties like Prabhat, Dhanlaxmi, Richharia, Turanta from the context documents. If you have seeds from BRBN, BAU, Sabour, NSC, or TDC, use them for irrigation. However, please note that this advice is based on the provided context documents and may not cover all specific c
> ... (1022 chars total)

---

### ✅ TC02: What is the current weather situation for farming in Kalahandi?
**Category:** Weather-Aware | **Score:** 4/5 | **Latency:** 21.43s

**Expected:** Show real-time weather data and relate it to contingency measures for Kalahandi, Odisha.

**Keyword Check:** All keywords OK

**Grading Reason:** The response provides relevant information about suitable crop varieties and farming practices for Kalahandi but does not specify the current weather data or relate it to contingency measures.

>  The current weather situation for farming in Kalahandi indicates that it is experiencing medium rainfall with lateritic soil and uplands. However, there is a delay of 2 weeks (as of June 4th week) due to early season drought. To cope with this, farmers are advised to grow short-duration, drought-tolerant varieties as sole crops such as Kalinga-II, Khandagiri, Vandana, Pathara, Parijata, Ghanteswari, Anjali for rice. For green gram and black gram, suggested varieties include PDM11 & 54, Hum1, T9
> ... (1132 chars total)

---

### ✅ TC03: Monsoon is delayed by 4 weeks in Solapur, what should I sow?
**Category:** Contingency | **Score:** 4/5 | **Latency:** 14.5s

**Expected:** Suggest drought-resistant crops based on ICAR Maharashtra contingency plans.

**Keyword Check:** All keywords OK

**Grading Reason:** The response directly addresses the query and suggests a drought-resistant crop, but it could have been more helpful by providing specific varieties of soybean recommended for Solapur district.

>  In Solapur, Maharashtra, with a 4-week delay in monsoon and severe deficit rainfall, it is recommended to prioritize drought contingency measures. From Document 5 (Bhandara), for early season drought conditions, consider changing your crop/cropping system including variety. For instance, you could sow soybean as suggested practices by Dr. PDKV.
> 
> However, the official ICAR-CRIDA district contingency plans in my database do not cover this specific query for Solapur, Maharashtra. It is advisable t
> ... (627 chars total)

---

### ✅ TC04: What are the flood contingency measures for rice in Puri district?
**Category:** Contingency | **Score:** 5/5 | **Latency:** 20.46s

**Expected:** Retrieve flood management advice from Odisha contingency plans.

**Keyword Check:** Missing: Odisha

**Grading Reason:** The AI response directly addresses the query and provides specific flood contingency measures for rice in Puri district, meeting the expected goal.

>  In Puri district during the Zaid (summer) season, if there is flooding, follow these suggested contingency measures for rice:
> 
> 1. Provide drainage for the nursery bed or go for resowing if not possible.
> 2. If necessary, perform wet seeding of sprouted seeds (75 kg/ha) of medium duration varieties like Lalat (120 days), Parijat (100 days), Konark (125 days), and Surendra (135 days).
> 50% Nitrogen (NV) and 50% Potassium (K2O) may be applied as basal and at the tillering stage.
> 
> In partially damage
> ... (1220 chars total)

---

### ✅ TC05: Rice stem borer control chemicals in Sundargarh Odisha
**Category:** Contingency | **Score:** 4/5 | **Latency:** 13.09s

**Expected:** Cite specific chemicals like triazophos, chlorpyriphos, or methyl demeton from Odisha plans.

**Keyword Check:** All keywords OK

**Grading Reason:** Directly addresses the query and cites specific chemicals, but does not provide explicit dosage information.

>  In Sundargarh, Odisha during the current Zaid (summer) season, to control rice stem borers, you can use methyl demeton or dimethioate as per the recommendations in Document 1 for Orissa 9 Sundargarh. The suggested dosage is not explicitly mentioned in the document, but it's advisable to consult local agricultural extension services for precise application rates. Keep in mind that the last 7 days have seen only 2.0mm of rainfall and the next 7 days are forecasted with no rain. Therefore, irrigat
> ... (546 chars total)

---

### ✅ TC06: What is the premium for rice in Kharif under PMFBY?
**Category:** Schemes | **Score:** 4/5 | **Latency:** 16.36s

**Expected:** Correctly state the 2% of sum insured rate for Kharif food crops.

**Keyword Check:** All keywords OK

**Grading Reason:** Answers the query but does not provide specific premium rate for rice in Kharif under PMFBY

>  The official ICAR-CRIDA contingency plans in my database do not cover the specific query about the premium for rice in Kharif under PMFBY. However, according to Document 1 (All India, Page 28), the Actuarial Premium Rate (APR) would be charged under PMFBY and RWBCIS by implementing Insurance Companies. The APR for Kharif all food grain and Oilseeds crops is 2.0% of Sum Insured or Actuarial rate, whichever is less as per Document 2 (All India, Page 29). Since the MSP for Paddy (Common) in Kharif
> ... (679 chars total)

---

### ✅ TC07: Am I eligible for PM-KISAN if I am a government employee?
**Category:** Schemes | **Score:** 5/5 | **Latency:** 9.64s

**Expected:** State that government employees are excluded from PM-KISAN benefits.

**Keyword Check:** All keywords OK

**Grading Reason:** The AI response directly addresses the query and meets the goal by citing specific exclusions for government employees in PM-KISAN scheme.

>  According to Document 2, all serving or retired officers and employees of central/state Government, PSUs, autonomous organizations, and local bodies are not eligible to get benefits under the PM-KISAN scheme. Therefore, if you are a government employee, you are not eligible for this scheme.

---

### ✅ TC08: How do I grow apples in Chennai?
**Category:** Guardrail | **Score:** 5/5 | **Latency:** 10.65s

**Expected:** Refuse with 'not in database' message. Must NOT suggest Shimla, Ooty, or any outside knowledge.

**Keyword Check:** All keywords OK

**Grading Reason:** Directly addresses the query and meets the goal by providing an accurate and specific response

>  The official ICAR-CRIDA contingency plans in my database do not cover growing apples in Chennai. Apples are not a native crop to India's tropical climate, especially in Chennai. It is highly unlikely that they can be successfully grown there without significant modifications to the environment and specialized care.

---

### ⚠️ TC09: Best fertilizer for coffee in Kerala?
**Category:** Guardrail | **Score:** 3/5 | **Latency:** 11.73s

**Expected:** Refuse — Kerala is not in the current database.

**Keyword Check:** Missing: database

**Grading Reason:** Answers the query but does not provide specific fertilizer recommendations for coffee in Kerala.

>  The official ICAR-CRIDA contingency plans do not cover the best fertilizer for coffee in Kerala. However, for general efficient fertilizer use, it is recommended to select the right kind of fertilizer according to the crop (coffee) and soil. Balanced fertilization should be practiced, and crops should only be sown at locally recommended periods. Farmers can get crop-specific nutrient recommendations after consulting their local extension service or DESAI-trainer and discussing with them the soi
> ... (621 chars total)

---

### ✅ TC10: Compare drought strategies between Solapur and Anantapur
**Category:** Cross-District | **Score:** 4/5 | **Latency:** 17.67s

**Expected:** Pull contingency data from both Maharashtra (Solapur) and Andhra Pradesh (Anantapur).

**Keyword Check:** All keywords OK

**Grading Reason:** Answer directly addresses the query and provides relevant information for Anantapur district, but lacks specific data for Solapur district to make a direct comparison

>  In Anantapur district of Andhra Pradesh, the current situation is severe deficit rainfall with high evapotranspiration. The official ICAR-CRIDA contingency plans suggest the following measures for mid-season drought (long dry spell) in Redgram and Groundnut crops:
> 
> 1. At vegetative stage: Protect the crop from Thrips using Chlorpyriphos at 2ml/L at 70 days interval, and mulching with groundnut shells is advised.
> 2. At reproductive stage: Supplemental irrigation with harvested rainwater in ponds
> ... (835 chars total)

---
# Agriculture RAG — Evaluation Report
**Date:** 2026-04-13 15:40
**Model:** mistral
**Test cases:** 2

## Summary
| Metric | Value |
|--------|-------|
| Average Score | **4.5 / 5** |
| Pass Rate (>=3) | **2/2** |
| Perfect (5/5) | **1/2** |
| Failures (<=1) | **0/2** |

## Scores by Category
| Category | Avg Score | Tests |
|----------|-----------|-------|
| Mandi-Price | 4.5 / 5 | 2 |

## Detailed Results

### ✅ TC11: What is the current onion price in Maharashtra and should I sell now?
**Category:** Mandi-Price | **Score:** 4/5 | **Latency:** 39.82s

**Expected:** Fetch live mandi prices, note no MSP for onion, and advise based on CRIDA plans.

**Keyword Check:** All keywords OK

**Grading Reason:** Answers the query but does not provide live prices or specific advice based on CRIDA plans

>  The official ICAR-CRIDA contingency plans do not provide real-time market prices for onions in Maharashtra. However, according to Mandi Price Data, the average modal price of onions in India is Rs.1611/quintal as of the provided data. In specific mandis within Maharashtra, Buland Shahr APMC offers a minimum price of Rs.1200/qtl and Jhansi APMC offers a minimum price of Rs.900/qtl for onions. If you are located in Maharashtra, you might want to refer to these prices as a reference. As for whethe
> ... (756 chars total)

---

### ✅ TC12: Wheat prices are crashing in Bihar, should I store or sell?
**Category:** Mandi-Price | **Score:** 5/5 | **Latency:** 26.58s

**Expected:** Fetch wheat prices, compare with MSP (Rs.2425/qtl), advise on storage or government procurement.

**Keyword Check:** All keywords OK

**Grading Reason:** Directly addresses the query, meets the goal, and provides specific district data.

>  Based on the current market price data for wheat in India, the average modal price is Rs.2427/quintal with a range of Rs.2200 to Rs.2588/quintal. In Bihar, the MSP for wheat is also Rs.2425/qtl. The market price in Bihar is currently at Rs.2410/qtl in Ahirora APMC and Rs.2405/qtl in Utraula APMC (both in Uttar Pradesh). In Sendhwa APMC of Madhya Pradesh, the price is lower at Rs.2200/qtl.
> 
> Given these prices, it might be beneficial to store your wheat if you expect prices to remain stable or in
> ... (1967 chars total)

---
