from tencent_doc_review import (
    get_default_review_rules_path,
    get_default_review_template_path,
    read_default_review_rules,
    read_default_review_template,
)


def test_default_review_template_is_available() -> None:
    path = get_default_review_template_path()
    content = read_default_review_template()

    assert path.endswith("default_product_research_structure_template.md")
    assert "产品概述" in content
    assert "结论与推荐建议" in content


def test_default_review_rules_is_available() -> None:
    path = get_default_review_rules_path()
    content = read_default_review_rules()

    assert path.endswith("default_product_research_review_rules.md")
    assert "语言问题审核" in content
    assert "事实核查" in content
