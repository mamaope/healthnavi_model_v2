from healthnavi.services.answer_composer import (
    build_answer_prompt,
    finalize_answer,
    format_reference_line,
    reference_display_title,
    strip_reference_section,
)


def _citations():
    return [
        {
            "number": 1,
            "title": "Consolidated Guidelines for the Prevention and Treatment of HIV in Uganda",
            "source_label": "Uganda Ministry of Health",
            "year": 2022,
            "url": "https://library.health.go.ug/hiv-guidelines.pdf#page=44",
        },
        {
            "number": 2,
            "title": "Updated recommendations on first-line and second-line antiretroviral regimens",
            "source_label": "WHO",
            "year": 2019,
            "url": "https://www.who.int/publications/i/item/WHO-CDS-HIV-19.15",
        },
        {
            "number": 3,
            "title": "Dolutegravir in pregnancy",
            "source_label": "PubMed",
            "year": 2021,
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        },
    ]


def test_prompt_contains_question_role_depth_and_numbered_sources():
    prompt = build_answer_prompt(
        query="First-line ART for a 30 year old woman in Kampala?",
        patient_data="First-line ART for a 30 year old woman in Kampala?",
        chat_history="",
        deep_search=False,
        user_role_from_db="Medical Officer",
        sources=[
            {
                "number": 1,
                "title": "Uganda HIV guidelines",
                "source_label": "Uganda Ministry of Health",
                "year": 2022,
                "url": "https://library.health.go.ug/hiv.pdf",
                "excerpt": "TDF + 3TC + DTG is the preferred first-line regimen for adults.",
            }
        ],
    )

    assert "You are Empirico" in prompt
    assert "SENIOR HOUSE OFFICER / MEDICAL OFFICER" in prompt
    assert "This is a quick answer" in prompt
    assert "## QUESTION\nFirst-line ART for a 30 year old woman in Kampala?" in prompt
    # Question and context are the same text, so no duplicate context block.
    assert "## ADDITIONAL CONTEXT" not in prompt
    assert "[1] Uganda HIV guidelines (Uganda Ministry of Health, 2022)" in prompt
    assert "Excerpt: TDF + 3TC + DTG is the preferred first-line regimen for adults." in prompt
    assert "Exam and revision requests" not in prompt


def test_prompt_demands_the_lowest_actionable_level():
    prompt = build_answer_prompt(
        query="Which antihypertensive should I start?",
        patient_data="Which antihypertensive should I start?",
        chat_history="",
        deep_search=False,
        user_role_from_db=None,
        sources=[],
    )

    assert "lowest actionable level" in prompt
    assert "A category is never the answer" in prompt
    # The contract is content, not headings for the model to print.
    assert "never headings to print" in prompt
    assert 'do not label sections "Decision"' in prompt


def test_prompt_uses_deep_rule_and_exam_rule_for_students():
    prompt = build_answer_prompt(
        query="Mechanism of action of dolutegravir",
        patient_data="Some extra context",
        chat_history="User asked about ART earlier.",
        deep_search=True,
        user_role_from_db="Clinical/Medical Student",
        sources=[],
    )

    assert "This is a deep answer" in prompt
    assert "MEDICAL STUDENT" in prompt
    assert "Exam and revision requests" in prompt
    assert "## ADDITIONAL CONTEXT\nSome extra context" in prompt
    assert "User asked about ART earlier." in prompt
    assert "No sources could be retrieved" in prompt


def test_prompt_states_the_citation_cap_and_marks_same_document_pages():
    prompt = build_answer_prompt(
        query="Q",
        patient_data="Q",
        chat_history="",
        deep_search=False,
        user_role_from_db=None,
        sources=[
            {
                "number": 1,
                "title": "Guideline, p. 23",
                "source_label": "WHO",
                "url": "https://x/c#page=23",
                "excerpt": "one",
            },
            {
                "number": 2,
                "title": "Guideline, p. 24",
                "source_label": "WHO",
                "url": "https://x/c#page=24",
                "excerpt": "two",
                "same_document_as": 1,
            },
        ],
        max_references=4,
    )

    assert "Cite at most 4 different sources" in prompt
    assert "[2] Guideline, p. 24 (WHO) - same document as [1], another page" in prompt


def test_finalize_links_markers_renumbers_by_first_use_and_builds_references():
    answer = (
        "Start **TDF + 3TC + DTG** as the preferred first-line regimen [2]. "
        "Ugandan guidance says the same and adds same-day initiation [1][2]. "
        "Dolutegravir is safe in pregnancy [3](https://wrong.example/link).\n\n"
        "**References**\n1. Made up by the model - https://example.org/fake"
    )

    display, used = finalize_answer(answer, _citations())

    body, _, references = display.partition("**References**")
    assert "Made up by the model" not in display
    assert "[1](https://www.who.int/publications/i/item/WHO-CDS-HIV-19.15)" in body
    assert (
        "[2](https://library.health.go.ug/hiv-guidelines.pdf#page=44)"
        "[1](https://www.who.int/publications/i/item/WHO-CDS-HIV-19.15)" in body
    )
    assert "[3](https://pubmed.ncbi.nlm.nih.gov/12345678/)" in body
    assert "wrong.example" not in display
    assert [c["number"] for c in used] == [1, 2, 3]
    assert used[0]["source_label"] == "WHO"
    assert used[1]["source_label"] == "Uganda Ministry of Health"
    assert (
        "1. [Updated recommendations on first-line and second-line antiretroviral regimens]"
        "(https://www.who.int/publications/i/item/WHO-CDS-HIV-19.15) - WHO, 2019" in references
    )
    assert (
        "2. [Consolidated Guidelines for the Prevention and Treatment of HIV in Uganda]"
        "(https://library.health.go.ug/hiv-guidelines.pdf#page=44) - Uganda Ministry of Health, 2022"
        in references
    )
    assert (
        "3. [Dolutegravir in pregnancy](https://pubmed.ncbi.nlm.nih.gov/12345678/) - PubMed, 2021"
        in references
    )


def test_finalize_drops_markers_that_do_not_exist_and_keeps_prose_intact():
    answer = "Use amoxicillin for 5 days [7]. Reassess at 48 hours [1, 9]."

    display, used = finalize_answer(answer, _citations()[:1])

    body = display.partition("**References**")[0].strip()
    assert body == (
        "Use amoxicillin for 5 days. Reassess at 48 hours "
        "[1](https://library.health.go.ug/hiv-guidelines.pdf#page=44)."
    )
    assert [c["number"] for c in used] == [1]


def test_finalize_handles_footnote_double_bracket_and_range_markers():
    answer = "Point A [[2]]. Point B [^1]. Point C [1-3]."

    display, used = finalize_answer(answer, _citations())

    body = display.partition("**References**")[0]
    assert body.count("](https://") == 5
    assert [c["title"][:12] for c in used] == ["Updated reco", "Consolidated", "Dolutegravir"]


def test_finalize_adds_no_references_when_model_cited_nothing():
    display, used = finalize_answer("An answer without any markers.", _citations())

    assert display == "An answer without any markers."
    assert used == []


def test_finalize_merges_markers_that_point_at_the_same_location():
    citations = [
        {
            "number": 1,
            "title": "Guideline, p. 23",
            "source_label": "WHO",
            "url": "https://iris.who.int/x/content#page=23",
        },
        {
            "number": 2,
            "title": "Guideline, p. 23",
            "source_label": "WHO",
            "url": "https://iris.who.int/x/content#page=23",
        },
        {
            "number": 3,
            "title": "News page",
            "source_label": "WHO",
            "url": "https://who.int/news/item#:~:text=Optimizing%20ART",
        },
        {
            "number": 4,
            "title": "News page",
            "source_label": "WHO",
            "url": "https://who.int/news/item#:~:text=Second%20line",
        },
        {
            "number": 5,
            "title": "Guideline, p. 24",
            "source_label": "WHO",
            "url": "https://iris.who.int/x/content#page=24",
        },
    ]

    display, used = finalize_answer(
        "Start ART now [1][2]. Prefer DTG [3][4]. Avoid EFV [5][1].", citations
    )

    body, _, references = display.partition("**References**")
    # Pages 23 and 24 are one document: one reference number, page-specific links kept.
    assert "Start ART now [1](https://iris.who.int/x/content#page=23)." in body
    assert "Prefer DTG [2](https://who.int/news/item#:~:text=Optimizing%20ART)." in body
    assert (
        "Avoid EFV [1](https://iris.who.int/x/content#page=24)"
        "[1](https://iris.who.int/x/content#page=23)." in body
    )
    assert [c["number"] for c in used] == [1, 2]
    assert "1. [Guideline](https://iris.who.int/x/content#page=23) - WHO" in references
    assert "2. [News page](https://who.int/news/item#:~:text=Optimizing%20ART) - WHO" in references
    assert "3." not in references


def test_finalize_caps_distinct_references_and_drops_markers_beyond_the_cap():
    citations = _citations() + [
        {"number": 4, "title": "Fourth source", "source_label": "CDC", "url": "https://cdc.gov/four"},
    ]
    answer = "A [3]. B [1]. C [4]. D [2][3]."

    display, used = finalize_answer(answer, citations, max_references=2)

    body, _, references = display.partition("**References**")
    assert body.strip() == (
        "A [1](https://pubmed.ncbi.nlm.nih.gov/12345678/). "
        "B [2](https://library.health.go.ug/hiv-guidelines.pdf#page=44). C. "
        "D [1](https://pubmed.ncbi.nlm.nih.gov/12345678/)."
    )
    assert [c["title"] for c in used] == [
        "Dolutegravir in pregnancy",
        "Consolidated Guidelines for the Prevention and Treatment of HIV in Uganda",
    ]
    assert "3." not in references


def test_finalize_without_citations_strips_markers_and_adds_no_references():
    display, used = finalize_answer("Give ORS [1] and zinc [2](http://x).", [])

    assert display == "Give ORS and zinc."
    assert used == []


def test_finalize_does_not_touch_markdown_or_spacing_in_prose():
    answer = (
        "## Management\n\n"
        "- **Ceftriaxone 1 g IV** once daily [1]\n"
        "- Check HbA1c and LiverTox listings; see [the WHO page](https://who.int/x) for detail.\n\n"
        "Follow-up in 2 weeks.  Two spaces kept? [1]"
    )

    display, _ = finalize_answer(answer, _citations()[:1])

    assert "## Management" in display
    assert (
        "- **Ceftriaxone 1 g IV** once daily "
        "[1](https://library.health.go.ug/hiv-guidelines.pdf#page=44)" in display
    )
    assert "HbA1c and LiverTox" in display
    assert "[the WHO page](https://who.int/x)" in display


def test_strip_reference_section_only_removes_trailing_list():
    answer = "Answer body.\n\nReferences\n1. Foo\n2. Bar"
    assert strip_reference_section(answer) == "Answer body."

    prose = "Sources of infection include water and food.\n\nTreat with ORS."
    assert strip_reference_section(prose) == prose


def test_reference_line_falls_back_to_url_slug_for_bad_titles():
    line = format_reference_line(
        4,
        {
            "title": "content",
            "source_label": "Guideline page",
            "year": None,
            "url": "https://health.go.ug/uganda-clinical-guidelines-2023.pdf",
        },
    )
    assert line == (
        "4. [uganda clinical guidelines 2023]"
        "(https://health.go.ug/uganda-clinical-guidelines-2023.pdf) - Guideline page"
    )


def test_reference_title_recovers_the_document_name_from_the_url_path():
    manual = {
        "title": "WHO Policy Platform",
        "source_label": "WHO",
        "url": (
            "https://platform.who.int/docs/default-source/mca-documents/policy-documents/"
            "operational-guidance/UGA-CH-33-01-OPERATIONAL-GUIDANCE-2012-eng-Manual-integrated-"
            "management-of-malaria-practical-guide-for-health-workers.pdf#page=87"
        ),
    }
    title = reference_display_title(1, manual)
    # The site name is replaced by the document the path names, with catalogue
    # codes and the language tag dropped.
    assert title.startswith("Operational Guidance 2012 Manual integrated management of malaria")
    assert "WHO Policy Platform" not in title
    assert "UGA" not in title and "eng" not in title.split()

    # A locator suffix is not part of the name, so it must not make a site name
    # look long enough to keep.
    pdf_link = {
        "title": "Download guidance (PDF), p. 16",
        "source_label": "NICE",
        "url": (
            "https://www.nice.org.uk/guidance/ng136/resources/"
            "hypertension-in-adults-diagnosis-and-management-pdf-66141722710213#page=16"
        ),
    }
    assert reference_display_title(1, pdf_link) == "hypertension in adults diagnosis and management"


def test_reference_title_keeps_a_real_document_title_and_an_uninformative_path():
    good = {
        "title": "Uganda Integrated Management of Acute Malnutrition Guidelines",
        "source_label": "Ministry of Health Uganda",
        "url": "https://platform.who.int/docs/UGA-CH-38-03-GUIDELINE-2016-eng-IMAM-Jan-2016.pdf#page=88",
    }
    assert "Uganda Integrated Management of Acute Malnutrition Guidelines" in format_reference_line(1, good)

    # A short title stays when the path has no document name to offer.
    thin_path = {
        "title": "WHO Regional Office for Africa",
        "source_label": "WHO AFRO",
        "url": "https://www.afro.who.int/sites/default/files/2017-05/casemgt.pdf#page=21",
    }
    assert "WHO Regional Office for Africa" in format_reference_line(1, thin_path)
