"""Provisional article grouping is deterministic and preserves uncertain matches."""

from jeromes_laboratory.literature.identity import ArticleMetadata, summarize_article_matches


def record(
    source_id: str, *, title: str | None = None, doi: str | None = None,
    author: str | None = None, journal: str | None = None, date: str | None = None,
    pmid: str | None = None, pmcid: str | None = None, source: str = "MED",
) -> ArticleMetadata:
    return ArticleMetadata(
        source, source_id, title, doi, pmid, pmcid, author, journal, date
    )


def test_exact_title_with_different_source_ids_is_provisionally_grouped() -> None:
    result = summarize_article_matches([
        record("1", title="A peptide for myostatin", author="Smith, A", date="2024-01-01"),
        record("2", title="A peptide for   myostatin.", author="Smith, A", date="2024-06-01"),
        record("3", title="Different study"),
    ])
    assert result.provisional_record_groups == 2
    assert result.additional_ids_in_groups == 1
    assert result.groups_with_metadata_differences == 0


def test_identifier_match_links_different_titles_and_flags_metadata_difference() -> None:
    result = summarize_article_matches([
        record("1", title="Early title", doi="https://doi.org/10.1000/ABC", date="2023"),
        record("2", title="Final title", doi="doi:10.1000/abc", date="2024"),
        record("3", title="Third title", pmid="123", pmcid="PMC123"),
        record("4", title="Fourth title", pmid="123"),
    ])
    assert result.provisional_record_groups == 2
    assert result.additional_ids_in_groups == 2
    assert result.groups_with_metadata_differences == 1


def test_missing_metadata_does_not_merge_unrelated_source_ids() -> None:
    result = summarize_article_matches([record("1"), record("2")])
    assert result.provisional_record_groups == 2
    assert result.additional_ids_in_groups == 0
    assert result.groups_with_metadata_differences == 0


def test_same_title_metadata_differences_are_reported_not_discarded() -> None:
    result = summarize_article_matches([
        record("1", title="Shared title", author="Smith", journal="Journal A", date="2020"),
        record("2", title="Shared title", author="Jones", journal="Journal B", date="2024"),
    ])
    assert result.provisional_record_groups == 1
    assert result.groups_with_metadata_differences == 1


def test_same_title_with_different_dois_is_flagged_for_review() -> None:
    result = summarize_article_matches([
        record("1", title="Shared title", doi="10.1000/one"),
        record("2", title="Shared title", doi="10.1000/two"),
    ])
    assert result.provisional_record_groups == 1
    assert result.groups_with_metadata_differences == 1


def test_patents_with_the_same_generic_title_remain_separate() -> None:
    result = summarize_article_matches([
        record("PAT1", title="ANTI-MYOSTATIN ANTIBODIES", source="PAT"),
        record("PAT2", title="ANTI-MYOSTATIN ANTIBODIES", source="PAT"),
        record("MED1", title="ANTI-MYOSTATIN ANTIBODIES"),
    ])
    assert result.provisional_record_groups == 3
    assert result.additional_ids_in_groups == 0
