from backend.services.report_service import generate_pdf_report
import io

def test_report():
    print("Testing PDF Generation...")
    metric = "avg_road_density"
    data = [
        {"district_name": "EAST KHASI HILLS", "avg_road_density": 0.85, "priority_rank": 1},
        {"district_name": "WEST KHASI HILLS", "avg_road_density": 0.45, "priority_rank": 2}
    ]
    summary = "This is a test summary for the GeoAI report."
    
    try:
        pdf_buffer = generate_pdf_report(metric, data, summary)
        print(f"Success! PDF Size: {len(pdf_buffer.getvalue())} bytes")
    except Exception as e:
        print(f"Failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_report()
