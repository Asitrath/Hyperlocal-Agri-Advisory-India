## Evaluation Summary (April 8, 2026)

### 📈 Metrics
| Query | Top Result Score | Location Accuracy | Content Relevance |
| :--- | :--- | :--- | :--- |
| Rice Pest (Odisha) | 0.485 | ✅ Correct (Sundargarh) | ✅ High (Pesticides listed) |
| Drought (Pune) | 0.704 | ⚠️ Mixed (Nasik/Purnea) | ✅ High (Drought strategies) |
| Kharif (Bihar) | 0.813 | ✅ Correct (Samastipur) | ✅ High (Sowing windows) |

### 💡 Key Findings
1. **Locality Bias:** The "Drought Pune" query returned Nasik and Purnea as top results. This suggests that while "Drought" matches well, the word "Pune" might need higher weighting or we should enforce a metadata filter when a user specifies a district.
2. **Technical Noise:** System logs show TensorFlow and oneDNN warnings. These do not affect accuracy but should be suppressed in a production UI.
3. **Chunking Performance:** The 1500-token chunks successfully captured entire rows of "Suggested Contingency Measures" from the tables.


## Evaluation Results - April 8, 2026

### 🧪 Test 3: Out-of-Distribution (Chennai Apples)
- **Query:** "How do I grow apples in Chennai?"
- **Status:** ❌ FAILED (Hallucination)
- **Issue:** The LLM ignored the "ONLY answer from context" constraint and provided general knowledge about Shimla/Ooty.
- **Fix Required:** Tighten the System Prompt or increase the "temperature" penalty for retrieving non-contextual data.

### 🧪 Test 4: Stem Borer (Odisha)
- **Query:** "Stem borer control chemical for rice in Odisha"
- **Status:** ✅ SUCCESS
- **Observations:** Successfully retrieved "Methyl demeton" and "Dimethioate." Accurately cited Orissa 9 (Sundargarh) and Orissa 15 (Boudh).