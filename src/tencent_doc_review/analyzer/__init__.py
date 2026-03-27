"""
内容分析引擎 - 核心模块

提供三种核心分析能力：
1. 事实核查 (Fact Checking) - 验证关键信息准确性
2. 结构匹配 (Structure Matching) - 对比模板结构完整性
3. 质量评估 (Quality Evaluation) - 多维度质量评分
"""

# 事实核查模块
from .fact_checker import (
    FactChecker,
    FactCheckResult,
    VerificationStatus,
    ClaimType,
    Claim,
    SearchClient,
    check_facts,
    extract_claims_only,
)

# 结构匹配模块
from .structure_matcher import (
    StructureMatcher,
    StructureMatchResult,
    MatchStatus,
    SectionType,
    Section,
    SectionMatch,
    match_structure,
    parse_document_structure,
)

# 质量评估模块
from .quality_evaluator import (
    QualityEvaluator,
    QualityReport,
    QualityDimension,
    QualityLevel,
    DimensionScore,
    evaluate_quality,
    quick_quality_score,
)
from .language_reviewer import LanguageReviewer
from .consistency_reviewer import ConsistencyReviewer

__all__ = [
    # 事实核查模块
    "FactChecker",
    "FactCheckResult",
    "VerificationStatus",
    "ClaimType",
    "Claim",
    "SearchClient",
    "check_facts",
    "extract_claims_only",
    
    # 结构匹配模块
    "StructureMatcher",
    "StructureMatchResult",
    "MatchStatus",
    "SectionType",
    "Section",
    "SectionMatch",
    "match_structure",
    "parse_document_structure",
    
    # 质量评估模块
    "QualityEvaluator",
    "QualityReport",
    "QualityDimension",
    "QualityLevel",
    "DimensionScore",
    "evaluate_quality",
    "quick_quality_score",
    "LanguageReviewer",
    "ConsistencyReviewer",
]
