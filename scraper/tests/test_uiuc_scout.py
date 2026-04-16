"""Tests for the UIUC scout normalization, ranking, and filtering logic."""

from __future__ import annotations

from uiuc_scout import build_opportunities, dedupe_opportunities, normalize_source_record, select_ping_candidates


class TestNormalizeSourceRecord:

    def test_live_ml_opening_becomes_technical_opening(self) -> None:
        record = {
            "source": "research_park",
            "url": "https://researchpark.illinois.edu/job/ml-compiler/",
            "entity_kind": "job_posting",
            "title": "Machine Learning Compiler Intern",
            "unit": "Research Park",
            "department": "Research Park",
            "faculty": "",
            "description": "Build compiler tooling for machine learning workloads and inference systems.",
            "contact": "",
            "last_seen": "2026-04-15",
            "status_hint": "open",
            "domain_tags": ["machine learning", "compiler", "systems"],
        }

        result = normalize_source_record(record)

        assert result is not None
        assert result["type"] == "uiuc_technical_opening"
        assert result["track"] == "ml_ai_research"
        assert result["next_action"] == "apply_now"
        assert result["company_archetypes"]
        assert "Nvidia" in result["company_archetypes"]
        assert result["should_ping"] is True

    def test_faculty_lab_becomes_outreach_target(self) -> None:
        record = {
            "source": "uiuc_seed",
            "url": "https://example.com/bo-li",
            "entity_kind": "faculty_profile",
            "title": "Bo Li - Trustworthy AI",
            "unit": "UIUC",
            "department": "CS",
            "faculty": "Bo Li",
            "description": "Research in trustworthy AI, robustness, privacy, and machine learning security.",
            "contact": "lbo@illinois.edu",
            "last_seen": "2026-04-15",
            "status_hint": "unknown",
            "domain_tags": ["trustworthy ai", "privacy", "robustness"],
        }

        result = normalize_source_record(record)

        assert result is not None
        assert result["type"] == "cold_outreach_target"
        assert result["track"] == "ml_ai_research"
        assert result["next_action"] == "reach_out"
        assert any("Trustworthy AI" in reason or "trustworthy" in reason.lower() for reason in result["fit_reasons"])

    def test_health_tech_opportunity_is_kept(self) -> None:
        record = {
            "source": "carle",
            "url": "https://example.com/eeg-ml",
            "entity_kind": "research_program",
            "title": "Machine Learning for EEG Analysis",
            "unit": "Carle Illinois",
            "department": "Bioengineering",
            "faculty": "Yogatheesan Varatharajah",
            "description": "Use machine learning to analyze EEG data for technical medical AI applications.",
            "contact": "",
            "last_seen": "2026-04-15",
            "status_hint": "rolling",
            "domain_tags": ["machine learning", "health-tech", "signals"],
        }

        result = normalize_source_record(record)

        assert result is not None
        assert result["track"] == "ml_ai_research"
        assert "health-tech" in result["tags"]

    def test_quant_opportunity_routes_to_quant_fintech(self) -> None:
        record = {
            "source": "gies_quant",
            "url": "https://example.com/quant-lab",
            "entity_kind": "research_group",
            "title": "Quantitative Finance Research Group",
            "unit": "UIUC",
            "department": "Gies",
            "faculty": "",
            "description": "Research in time series forecasting, optimization, risk, and systematic trading.",
            "contact": "",
            "last_seen": "2026-04-15",
            "status_hint": "rolling",
            "domain_tags": ["quant", "time series", "trading", "optimization"],
        }

        result = normalize_source_record(record)

        assert result is not None
        assert result["track"] == "quant_fintech"
        assert "Jane Street" in result["company_archetypes"]

    def test_hidden_pathway_record_can_become_outreach_target(self) -> None:
        record = {
            "source": "uiuc_ml_seminar",
            "url": "https://publish.illinois.edu/ml-seminar/",
            "entity_kind": "research_group",
            "title": "Illinois Machine Learning Seminar",
            "unit": "Siebel School",
            "department": "ML Seminar",
            "faculty": "",
            "description": "Official Illinois seminar with machine learning, NLP, trustworthy AI, student presenters, and research lab connections.",
            "contact": "",
            "last_seen": "2026-04-16",
            "status_hint": "unknown",
            "domain_tags": ["machine learning", "nlp", "trustworthy ai", "seminar", "research"],
            "hidden_pathway_signal": True,
            "officiality": "official",
            "pathway_kind": "seminar",
            "student_access_signals": ["student", "seminar", "presenters"],
            "hidden_pathway_score": 25,
            "pathway_recommended_action": "reach_out",
        }

        result = normalize_source_record(record)

        assert result is not None
        assert result["type"] == "cold_outreach_target"
        assert result["next_action"] == "reach_out"
        assert "hidden_pathway_signals" in result

    def test_non_technical_campus_role_is_filtered_out(self) -> None:
        record = {
            "source": "campus_jobs",
            "url": "https://example.com/front-desk",
            "entity_kind": "job_posting",
            "title": "Front Desk Student Assistant",
            "unit": "UIUC",
            "department": "Housing",
            "faculty": "",
            "description": "Help students at the front desk and answer phones.",
            "contact": "",
            "last_seen": "2026-04-15",
            "status_hint": "open",
            "domain_tags": [],
        }

        assert normalize_source_record(record) is None

    def test_ai_substring_inside_other_words_does_not_create_false_positive(self) -> None:
        record = {
            "source": "research_park",
            "url": "https://example.com/gentiva",
            "entity_kind": "research_group",
            "title": "Gentiva (SouthernCare Inc.)",
            "unit": "Research Park",
            "department": "Research Park",
            "faculty": "",
            "description": "Home health and hospice services in Champaign with palliative care support.",
            "contact": "",
            "last_seen": "2026-04-15",
            "status_hint": "rolling",
            "domain_tags": ["tenant directory", "biotech and healthcare"],
        }

        assert normalize_source_record(record) is None


class TestDedupeOpportunities:

    def test_merges_duplicate_urls_and_keeps_higher_score(self) -> None:
        first = {
            "id": "one",
            "url": "https://example.com/opportunity",
            "title": "ML Research Opportunity",
            "total_score": 72,
            "fit_reasons": ["Research fit"],
        }
        second = {
            **first,
            "id": "two",
            "total_score": 89,
            "fit_reasons": ["Research fit", "NLP fit"],
        }

        deduped = dedupe_opportunities([first, second])

        assert len(deduped) == 1
        assert deduped[0]["total_score"] == 89


class TestSelectPingCandidates:

    def test_selects_top_high_fit_items_only(self) -> None:
        opportunities = [
            {"title": "A", "total_score": 104, "should_ping": True},
            {"title": "B", "total_score": 99, "should_ping": True},
            {"title": "C", "total_score": 97, "should_ping": True},
            {"title": "D", "total_score": 96, "should_ping": True},
            {"title": "E", "total_score": 88, "should_ping": False},
        ]

        selected = select_ping_candidates(opportunities, limit=3)

        assert [item["title"] for item in selected] == ["A", "B", "C"]


class TestBuildOpportunitiesWithAlumniFeedback:

    def test_alumni_backed_source_becomes_outreach_target(self) -> None:
        records = [
            {
                "source": "uiuc_alumni_pattern",
                "url": "https://spin.ncsa.illinois.edu/",
                "entity_kind": "research_program",
                "title": "NCSA SPIN",
                "unit": "NCSA",
                "department": "SPIN",
                "faculty": "",
                "description": "Alumni-backed Illinois pathway seen across 3 UIUC LinkedIn-style profiles. Paths: ml_ai_research.",
                "contact": "",
                "last_seen": "2026-04-16",
                "status_hint": "rolling",
                "domain_tags": ["machine learning", "research engineer"],
                "alumni_evidence_count": 3,
                "alumni_patterns": ["NCSA SPIN"],
                "evidence_sources": ["alumni"],
            }
        ]
        patterns = [
            {
                "id": "program:ncsa-spin",
                "entity_type": "program",
                "entity_name": "NCSA SPIN",
                "entity_url": "https://spin.ncsa.illinois.edu/",
                "evidence_count": 3,
                "sample_profiles": [],
                "path_tags": ["ml_ai_research"],
                "fit_reasons": ["Repeated UIUC pattern"],
                "recommended_action": "reach_out",
                "score": 44,
                "illinois_connected": True,
            }
        ]

        opportunities = build_opportunities(records, alumni_patterns=patterns)

        assert len(opportunities) == 1
        assert opportunities[0]["type"] == "research_opening"
        assert opportunities[0]["evidence_sources"] == ["alumni"]
        assert opportunities[0]["alumni_evidence_count"] == 3

    def test_hidden_pathway_boosts_related_opportunity_without_duplication(self) -> None:
        records = [
            {
                "source": "ncsa_spin",
                "url": "https://spin.ncsa.illinois.edu/",
                "entity_kind": "research_program",
                "title": "NCSA SPIN",
                "unit": "NCSA",
                "department": "SPIN",
                "faculty": "",
                "description": "Student program for machine learning research software and data systems work.",
                "contact": "",
                "last_seen": "2026-04-16",
                "status_hint": "rolling",
                "domain_tags": ["machine learning", "research software", "data systems"],
            }
        ]
        hidden_pathway_records = [
            {
                "source": "uiuc_ml_pathway",
                "url": "https://spin.ncsa.illinois.edu/",
                "entity_kind": "research_program",
                "title": "NCSA SPIN",
                "unit": "NCSA",
                "department": "SPIN",
                "faculty": "",
                "description": "Repeated Illinois student pathway into ML research and research engineering.",
                "contact": "",
                "last_seen": "2026-04-16",
                "status_hint": "unknown",
                "domain_tags": ["machine learning", "research engineer"],
                "hidden_pathway_signal": True,
                "officiality": "official",
                "pathway_kind": "program",
                "student_access_signals": ["student", "apply", "research"],
                "hidden_pathway_score": 24,
                "pathway_recommended_action": "reach_out",
            }
        ]

        opportunities = build_opportunities(records, hidden_pathway_records=hidden_pathway_records)

        assert len(opportunities) == 1
        assert "hidden_pathways" in opportunities[0]["evidence_sources"]
        assert "NCSA SPIN" in opportunities[0]["hidden_pathway_signals"]
        assert opportunities[0]["score_components"]["pathway_leverage"] >= 12
