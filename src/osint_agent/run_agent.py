from graph import app


def run_osint_agent(applicant_name, applicant_dob=None):
    result = app.invoke({
        "applicant_name": applicant_name,
        "applicant_dob": applicant_dob,
        "ofac_result": {},
        "raw_results": [],
        "filtered_results": [],
        "risk_summary": "",
        "risk_flag": ""
    })
    return result


if __name__ == "__main__":
    result = run_osint_agent("Viktor Kessler", applicant_dob="1975-06-12")

    print(f"OFAC result: {result['ofac_result']}")
    print(f"\nRisk summary:\n{result['risk_summary']}")
    print(f"\nRisk flag: {result['risk_flag']}")