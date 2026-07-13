from graph import app


def run_osint_agent(applicant_name):
    """Run the full OSINT agent pipeline for one applicant."""
    result = app.invoke({
        "applicant_name": applicant_name,
        "raw_results": [],
        "filtered_results": [],
        "risk_summary": "",
        "risk_flag": ""
    })
    return result


if __name__ == "__main__":
    test_name = "Jane Doe"
    result = run_osint_agent(test_name)

    print(f"\nApplicant: {test_name}")
    print(f"Raw results found: {len(result['raw_results'])}")
    print(f"After filtering: {len(result['filtered_results'])}")
    print(f"\nRisk summary:\n{result['risk_summary']}")
    print(f"\nRisk flag: {result['risk_flag']}")