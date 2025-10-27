import fitz  # PyMuPDF
import re
import json

# Missing lessons to extract
missing_lessons = {
    "module-1": [
        {"lesson": 3, "title": "Protégé Eligibility"},
        {"lesson": 4, "title": "Agreements, Policy & Reporting"}
    ],
    "module-2": [
        {"lesson": 2, "title": "Associate Director, DoD Mentor-Protégé Program"},
        {"lesson": 3, "title": "Services/Defense Agencies' Director, Small Business Programs"},
        {"lesson": 6, "title": "MPP Support Staff (DoD OSBP)"},
        {"lesson": 9, "title": "Defense Contract Management Agency (DCMA)"}
    ],
    "module-4": [
        {"lesson": 2, "title": "Agreement Development and Proposal Requirements"}
    ],
    "module-6": [
        {"lesson": 2, "title": "Reporting Excellence - SARs and Performance Measurement"}
    ],
    "module-8": [
        {"lesson": 3, "title": "Third-Party Integration and Reporting Excellence"}
    ]
}

pdf_files = {
    "module-1": "../Modules/module-1-do-d-mentor-protege-program-IDnloot1.pdf",
    "module-2": "../Modules/module-2-do-d-mentor-protege-program-roles-responsibilities-OaVLpCBp.pdf",
    "module-4": "../Modules/module-4-mentor-eligibility-agreement-development-approval-processes-fr5ns6BS.pdf",
    "module-6": "../Modules/module-6-performance-monitoring-and-compliance-in3tzbro.pdf",
    "module-8": "../Modules/module-8-subcontracting-small-business-participation-EnD4WLwB.pdf"
}

results = {}

for module_key, lessons in missing_lessons.items():
    if module_key not in pdf_files:
        continue

    pdf_path = pdf_files[module_key]
    results[module_key] = []

    try:
        doc = fitz.open(pdf_path)

        for lesson_info in lessons:
            lesson_num = lesson_info["lesson"]
            lesson_title = lesson_info["title"]

            print(f"\nSearching {module_key} Lesson {lesson_num}: {lesson_title}")

            # Search for the lesson
            found_objectives = []
            found_lesson = False
            capture_objectives = False
            objectives_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                # Look for the lesson header
                lesson_pattern = f"Lesson {lesson_num}"
                if lesson_pattern in text and not found_lesson:
                    found_lesson = True
                    print(f"  Found lesson on page {page_num + 1}")

                # Look for "Learning Objectives" section
                if found_lesson and "Learning Objec" in text:
                    capture_objectives = True
                    # Extract the objectives section
                    lines = text.split('\n')
                    in_objectives = False

                    for i, line in enumerate(lines):
                        if 'Learning Objec' in line:
                            in_objectives = True
                            continue

                        if in_objectives:
                            # Stop if we hit another section header or end
                            if any(keyword in line for keyword in ['Welcome to', 'CONTINUE', 'Summary', 'Module', 'Lesson', 'Assessment']) and len(objectives_text) > 2:
                                break

                            # Clean and add objective
                            cleaned = line.strip()
                            if cleaned and len(cleaned) > 10 and not cleaned.startswith('Page'):
                                # Remove bullet points and clean up
                                cleaned = re.sub(r'^[•\-\*]+\s*', '', cleaned)
                                if cleaned:
                                    objectives_text.append(cleaned)

                    if objectives_text:
                        found_objectives = objectives_text[:10]  # Limit to reasonable number
                        break

                # Stop searching after we've gone too far past the lesson
                if found_lesson and page_num > 50:
                    break

            results[module_key].append({
                "lesson": lesson_num,
                "title": lesson_title,
                "objectives": found_objectives if found_objectives else ["Not extracted"]
            })

        doc.close()

    except Exception as e:
        print(f"Error processing {module_key}: {e}")
        results[module_key].append({
            "error": str(e)
        })

# Print results
print("\n" + "="*80)
print("EXTRACTED LEARNING OBJECTIVES")
print("="*80)

for module_key, lesson_data in results.items():
    print(f"\n{module_key.upper()}:")
    for lesson in lesson_data:
        if "error" in lesson:
            print(f"  ERROR: {lesson['error']}")
        else:
            print(f"\n  Lesson {lesson['lesson']}: {lesson['title']}")
            print("  Learning Objectives:")
            for obj in lesson['objectives']:
                print(f"    - {obj}")

# Save to JSON
with open('missing_objectives.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n\nResults saved to missing_objectives.json")
