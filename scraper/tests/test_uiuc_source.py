"""Tests for UIUC source parsing helpers."""

from __future__ import annotations

from sources.uiuc import (
    parse_faculty_link_hub,
    parse_faculty_profile_page,
    parse_generic,
    parse_hidden_pathway_page,
    parse_research_park_company_page,
    parse_research_park_sitemap,
    parse_self_page,
)


def test_parse_generic_keeps_real_research_links_and_filters_noise() -> None:
    html = """
    <html><body>
      <a href="/reu">Research Experiences for Undergraduates (REU)</a>
      <a href="/faculty-student">Faculty and Student Opportunities</a>
      <a href="/office">Office of Undergraduate Research</a>
      <a href="/certificate">Learn more about the Undergraduate Research Certificate</a>
      <a href="/conference">3rd Annual NCSA Students Research Conference</a>
    </body></html>
    """
    page = {
        "source": "undergrad_research",
        "url": "https://example.edu/research",
        "entity_kind": "research_program",
        "unit": "Illinois",
        "department": "Illinois",
    }

    results = parse_generic(html, page)

    titles = [record["title"] for record in results]
    assert "Research Experiences for Undergraduates (REU)" in titles
    assert "Faculty and Student Opportunities" in titles
    assert "Office of Undergraduate Research" not in titles
    assert "Learn more about the Undergraduate Research Certificate" not in titles
    assert "3rd Annual NCSA Students Research Conference" not in titles


def test_parse_research_park_sitemap_extracts_company_urls() -> None:
    xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://researchpark.illinois.edu/aganswers-ai-inc/</loc></url>
      <url><loc>https://researchpark.illinois.edu/champaign-caterpillar-innovation-center/</loc></url>
      <url><loc>https://researchpark.illinois.edu/agtech-summit-2026/</loc></url>
    </urlset>
    """

    urls = parse_research_park_sitemap(xml)

    assert "https://researchpark.illinois.edu/aganswers-ai-inc/" in urls
    assert "https://researchpark.illinois.edu/champaign-caterpillar-innovation-center/" in urls
    assert "https://researchpark.illinois.edu/agtech-summit-2026/" not in urls


def test_parse_research_park_company_page_extracts_technical_signals() -> None:
    html = """
    <html>
      <head>
        <meta name="description" content="Research and development efforts including engineering, computer science, operations research, statistics, and data analysis." />
      </head>
      <body>
        <script type="application/ld+json">
        {"@graph":[
          {"@type":"BlogPosting","headline":"Champaign Caterpillar Innovation Center","articleSection":"Corporate Innovation Site, Software, AI and Analytics, Tenant Directory"},
          {"@type":"WebPage","name":"Champaign Caterpillar Innovation Center | Research Park"}
        ]}
        </script>
      </body>
    </html>
    """

    record = parse_research_park_company_page(
        html,
        "https://researchpark.illinois.edu/champaign-caterpillar-innovation-center/",
    )

    assert record is not None
    assert record["title"] == "Champaign Caterpillar Innovation Center"
    assert "software" in [tag.lower() for tag in record["domain_tags"]]
    assert "ai" in [tag.lower() for tag in record["domain_tags"]]
    assert "computer science" in record["description"].lower()


def test_parse_research_park_company_page_filters_resource_and_news_pages() -> None:
    html = """
    <html>
      <head>
        <meta name="description" content="Campus resources for tenants and startups." />
      </head>
      <body>
        <script type="application/ld+json">
        {"@graph":[
          {"@type":"BlogPosting","headline":"Campus Resources","articleSection":"Resources"},
          {"@type":"WebPage","name":"Campus Resources | Research Park"}
        ]}
        </script>
      </body>
    </html>
    """

    record = parse_research_park_company_page(
        html,
        "https://researchpark.illinois.edu/campus-resources/",
    )

    assert record is None


def test_parse_research_park_company_page_ignores_ai_substrings_inside_words() -> None:
    html = """
    <html>
      <head>
        <meta name="description" content="Home health and hospice services in Champaign with palliative care support." />
      </head>
      <body>
        <script type="application/ld+json">
        {"@graph":[
          {"@type":"BlogPosting","headline":"Gentiva (SouthernCare Inc.)","articleSection":"Biotech and Healthcare, Tenant Directory"},
          {"@type":"WebPage","name":"Gentiva (SouthernCare Inc.) | Research Park"}
        ]}
        </script>
      </body>
    </html>
    """

    record = parse_research_park_company_page(
        html,
        "https://researchpark.illinois.edu/gentiva-southerncare-inc/",
    )

    assert record is None


def test_parse_faculty_link_hub_extracts_profile_urls() -> None:
    html = """
    <html><body>
      <a href="/about/directory/faculty/aschwing">Alexander Schwing</a>
      <a href="/about/directory/faculty/huanz">Huan Zhang</a>
      <a href="/academics/courses/profile/ECE549">ECE 549</a>
      <a href="/about/jobs/faculty-tenure-track">Faculty</a>
    </body></html>
    """
    page = {
        "source": "ece_ai_faculty",
        "url": "https://ece.illinois.edu/research/crosscutting-themes/ai",
        "unit": "UIUC",
        "department": "ECE",
    }

    urls = parse_faculty_link_hub(html, page)

    assert "https://ece.illinois.edu/about/directory/faculty/aschwing" in urls
    assert "https://ece.illinois.edu/about/directory/faculty/huanz" in urls
    assert not any("ECE549" in url for url in urls)


def test_parse_faculty_link_hub_respects_profile_path_pattern() -> None:
    html = """
    <html><body>
      <a href="/directory/profile/jtalliso">Jordan Tallis</a>
      <a href="/directory/faculty/awards">Awards</a>
      <a href="/people/contact-us">Contact Us</a>
    </body></html>
    """
    page = {
        "source": "ise_faculty",
        "url": "https://ise.illinois.edu/directory/faculty",
        "unit": "UIUC",
        "department": "ISE",
        "profile_link_pattern": "/directory/profile/",
    }

    urls = parse_faculty_link_hub(html, page)

    assert urls == ["https://ise.illinois.edu/directory/profile/jtalliso"]


def test_parse_faculty_link_hub_extracts_directory_profile_urls() -> None:
    html = """
    <html><body>
      <a href="/directory/profile/jagt">Joshua Agterberg</a>
      <a href="/directory/profile/mjjang">Min Jee Jang</a>
      <a href="/directory">Directory</a>
      <a href="/people/faculty">Faculty</a>
    </body></html>
    """
    page = {
        "source": "statistics_faculty",
        "url": "https://stat.illinois.edu/directory",
        "unit": "UIUC",
        "department": "Statistics",
    }

    urls = parse_faculty_link_hub(html, page)

    assert "https://stat.illinois.edu/directory/profile/jagt" in urls
    assert "https://stat.illinois.edu/directory/profile/mjjang" in urls
    assert "https://stat.illinois.edu/directory" not in urls


def test_parse_faculty_profile_page_keeps_relevant_ml_faculty() -> None:
    html = """
    <html>
      <head>
        <title>Alexander Schwing | Electrical &amp; Computer Engineering | Illinois</title>
        <meta name="description" content="Alexander Schwing" />
      </head>
      <body>
        <h2>Research Interests</h2>
        <p>Machine learning, computer vision, multimodal reasoning, and generative models.</p>
      </body>
    </html>
    """
    page = {
        "source": "ece_ai_faculty",
        "url": "https://ece.illinois.edu/research/crosscutting-themes/ai",
        "unit": "UIUC",
        "department": "ECE",
    }

    record = parse_faculty_profile_page(
        html,
        "https://ece.illinois.edu/about/directory/faculty/aschwing",
        page,
    )

    assert record is not None
    assert record["title"] == "Alexander Schwing"
    assert "computer vision" in record["domain_tags"]
    assert record["department"] == "ECE"


def test_parse_faculty_profile_page_keeps_relevant_statistics_faculty() -> None:
    html = """
    <html>
      <head>
        <title>Joshua Agterberg | Statistics at Illinois</title>
        <meta name="description" content="Assistant Professor, Data Science and Big Data Analytics" />
      </head>
      <body>
        <h2>Research Areas</h2>
        <p>Data Science and Big Data Analytics</p>
        <p>Scaling laws for neural language models on the gender gaps in natural language processing.</p>
        <p>Continual learning of knowledge graphs.</p>
      </body>
    </html>
    """
    page = {
        "source": "statistics_faculty",
        "url": "https://stat.illinois.edu/directory",
        "unit": "UIUC",
        "department": "Statistics",
    }

    record = parse_faculty_profile_page(
        html,
        "https://stat.illinois.edu/directory/profile/jagt",
        page,
    )

    assert record is not None
    assert record["title"] == "Joshua Agterberg"
    assert "natural language" in record["domain_tags"]
    assert record["department"] == "Statistics"


def test_parse_self_page_keeps_relevant_program_page() -> None:
    html = """
    <html>
      <head>
        <title>Data Science Research Service | Gies College of Business | UIUC</title>
        <meta name="description" content="Support in data science, machine learning, computational infrastructure, and data acquisition." />
      </head>
      <body>
        <p>Students, faculty, and staff can request help for data analytics and machine learning research.</p>
      </body>
    </html>
    """
    page = {
        "source": "gies_dsrs",
        "url": "https://giesbusiness.illinois.edu/dsrs",
        "entity_kind": "research_program",
        "unit": "Gies",
        "department": "Data Science Research Service",
    }

    records = parse_self_page(html, page)

    assert len(records) == 1
    assert records[0]["title"] == "Data Science Research Service"
    assert "machine learning" in records[0]["domain_tags"]


def test_parse_hidden_pathway_page_keeps_official_research_route() -> None:
    html = """
    <html>
      <head>
        <title>Illinois Machine Learning Seminar | Illinois</title>
        <meta name="description" content="Weekly seminar on machine learning, NLP, computer vision, and trustworthy AI with student presenters and research discussions." />
        <style>.wp-block-cover{display:flex}</style>
      </head>
      <body>
        <script>function themeInit(){ return true; }</script>
        <p>Undergraduate and graduate students can join seminar discussions, present work, and connect with research labs.</p>
      </body>
    </html>
    """
    page = {
        "source": "uiuc_ml_seminar",
        "url": "https://publish.illinois.edu/ml-seminar/",
        "entity_kind": "research_program",
        "unit": "Siebel School of Computing and Data Science",
        "department": "ML Seminar",
        "officiality": "official",
        "pathway_kind": "seminar",
    }

    records = parse_hidden_pathway_page(html, page)

    assert len(records) == 1
    assert records[0]["hidden_pathway_signal"] is True
    assert records[0]["officiality"] == "official"
    assert "machine learning" in records[0]["domain_tags"]
    assert "seminar" in records[0]["student_access_signals"]
    assert "wp-block-cover" not in records[0]["description"]


def test_parse_hidden_pathway_page_filters_generic_social_group() -> None:
    html = """
    <html>
      <head>
        <title>Illinois Social Dance Club | Illinois</title>
        <meta name="description" content="Join our social dance club for concerts, tailgates, and alumni weekend events." />
      </head>
      <body>
        <p>Meet friends at fundraisers, tailgates, and social events all semester.</p>
      </body>
    </html>
    """
    page = {
        "source": "dance_club",
        "url": "https://example.com/dance",
        "entity_kind": "research_program",
        "unit": "Illinois",
        "department": "Student Life",
        "officiality": "affiliated",
        "pathway_kind": "student_org",
    }

    assert parse_hidden_pathway_page(html, page) == []


def test_parse_hidden_pathway_page_uses_paragraph_fallback_for_summary() -> None:
    html = """
    <html>
      <head>
        <title>Illinois Scholars Undergraduate Research Program | Illinois</title>
        <style>.wp-block-cover{display:flex}</style>
      </head>
      <body>
        <script>function OptanonWrapper() { }</script>
        <p>The Illinois Scholars Undergraduate Research program helps undergraduates find research mentors and build strong application materials.</p>
        <p>Students can join workshops, connect with labs, and explore long-term ML and data science pathways.</p>
      </body>
    </html>
    """
    page = {
        "source": "isur_program",
        "url": "https://isur.engineering.illinois.edu/",
        "entity_kind": "research_program",
        "unit": "Grainger",
        "department": "ISUR",
        "officiality": "official",
        "pathway_kind": "program",
    }

    records = parse_hidden_pathway_page(html, page)

    assert len(records) == 1
    assert records[0]["description"].startswith("The Illinois Scholars Undergraduate Research program")
    assert "OptanonWrapper" not in records[0]["description"]
    assert "wp-block-cover" not in records[0]["description"]
