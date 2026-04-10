import json
import time
import os
from datetime import datetime
from query_rag import ask  # Import your core pipeline

# 🎯 The Golden Dataset: Questions + Expected Key Info
# This set covers all your project pillars: Weather, Contingency, Schemes, and Safety.
TEST_CASES = [
    {
        "id": "TC01",
        "category": "Weather-Aware",
        "query": "Should I irrigate my rice crop in Patna today?",
        "expected_goal": "Identify rainfall deficit from live data and recommend life-saving irrigation."
    },
    {
        "id": "TC02",
        "category": "Contingency",
        "query": "Monsoon is delayed by 4 weeks in Solapur, what should I sow?",
        "expected_goal": "Suggest drought-resistant crops (e.g., Pearl Millet) based on ICAR Maharashtra plans."
    },
    {
        "id": "TC03",
        "category": "Schemes",
        "query": "What is the premium for rice in Kharif under PMFBY?",
        "expected_goal": "Correctly state the 2% sum insured rate for Kharif crops."
    },
    {
        "id": "TC04",
        "category": "Safety/Guardrail",
        "query": "How do I grow apples in Chennai?",
        "expected_goal": "Trigger the 'not in database' refusal message and avoid hallucinations."
    },
    {
        "id": "TC05",
        "category": "Troubleshooting",
        "query": "How to apply for PM-KISAN if I lost my Aadhaar?",
        "expected_goal": "Retrieve the 'Edit Aadhaar Failure Record' portal instructions."
    }
]


def run_evaluation_suite():
    print(f"{'=' * 60}")
    print(f"🚀 Starting Automated Evaluation Suite: {len(TEST_CASES)} cases")
    print(f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    results = []

    for case in TEST_CASES:
        print(f"🔍 Running [{case['id']}] ({case['category']})")
        print(f"❓ Query: {case['query']}")

        start_time = time.time()

        # We capture the output by calling your ask() function.
        # Note: your ask() function already prints to console,
        # so this script will show the generation in real-time.
        try:
            response = ask(case['query'], verbose=False, use_weather=True)
            latency = round(time.time() - start_time, 2)

            results.append({
                "id": case['id'],
                "category": case['category'],
                "query": case['query'],
                "expected_logic": case['expected_goal'],
                "bot_response": response,
                "latency_sec": latency,
                "status": "COMPLETED"
            })
            print(f"✅ Completed in {latency}s\n")

        except Exception as e:
            print(f"❌ Error during execution: {e}\n")
            results.append({
                "id": case['id'],
                "query": case['query'],
                "status": "FAILED",
                "error": str(e)
            })

    # 📁 Save results to a timestamped JSON file
    os.makedirs("evaluation_logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"evaluation_logs/eval_report_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"{'=' * 60}")
    print(f"✨ Evaluation complete!")
    print(f"📂 Results saved to: {filename}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    # Ensure Ollama is running before starting
    run_evaluation_suite()